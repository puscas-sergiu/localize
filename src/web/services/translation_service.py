"""Translation service that adapts CLI translation logic for web use."""

import asyncio
from typing import Callable, Optional
from dataclasses import dataclass, asdict

from ...extraction.xcstrings_parser import XCStringsParser
from ...extraction.xcstrings_writer import XCStringsWriter
from ...translation.translator import HybridTranslator, TranslationStats
from ...validation.llm_reviewer import LLMReviewer, BulkReviewResult
from ...config import config

# Import for type hints only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .review_history import ReviewHistoryService


@dataclass
class TranslationJobResult:
    """Result of a translation job."""
    success: bool
    languages_processed: list[str]
    stats_by_language: dict[str, dict]
    error: Optional[str] = None


@dataclass
class VerificationJobResult:
    """Result of a verification job."""
    success: bool
    total_reviewed: int
    passed: int
    needs_attention: int
    issues: list[dict]
    has_more: bool = False
    total_unreviewed: int = 0
    next_offset: int = 0
    auto_reviewed_count: int = 0  # Number of passed strings auto-marked as reviewed
    skipped_unchanged: int = 0  # Number of strings skipped (already reviewed, unchanged)
    error: Optional[str] = None


class TranslationService:
    """
    Adapts CLI translation logic for web use.

    Provides async wrappers around synchronous translation code.
    """

    def __init__(self):
        self.parser = XCStringsParser()
        self.writer = XCStringsWriter()

    async def translate_file(
        self,
        file_content: str,
        languages: list[str],
        quality_threshold: float = 80.0,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[str, TranslationJobResult]:
        """
        Translate an xcstrings file to specified languages.

        Args:
            file_content: JSON content of the .xcstrings file
            languages: List of target language codes
            quality_threshold: Score threshold for GPT-4 fallback
            progress_callback: Async callback(current, total, message, language, **extra)

        Returns:
            Tuple of (translated_json_string, TranslationJobResult)
        """
        try:
            # Parse the file
            xcstrings = self.parser.parse_string(file_content)
            all_strings = xcstrings.get_translatable_strings()

            stats_by_language = {}
            total_languages = len(languages)

            for lang_idx, lang in enumerate(languages):
                # Get strings that need translation for this language
                strings_to_translate = {
                    k: v for k, v in all_strings.items()
                    if k in xcstrings.strings and not xcstrings.strings[k].has_translation(lang)
                }

                if not strings_to_translate:
                    if progress_callback:
                        await progress_callback(
                            lang_idx + 1,
                            total_languages,
                            f"All strings already translated for {lang}",
                            lang,
                            skipped=True,
                        )
                    continue

                # Create translator
                translator = HybridTranslator(quality_threshold=quality_threshold)

                # Create a sync progress callback that queues updates
                progress_queue = asyncio.Queue()

                def sync_progress(current: int, total: int, message: str):
                    """Sync callback that puts updates in queue."""
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.run_coroutine_threadsafe(
                                progress_queue.put((current, total, message)),
                                loop
                            )
                    except Exception:
                        pass

                # Run translation in thread pool
                async def run_translation():
                    return await asyncio.to_thread(
                        translator.translate_batch,
                        strings_to_translate,
                        lang,
                        None,  # context
                        sync_progress,
                    )

                # Start translation task
                translation_task = asyncio.create_task(run_translation())

                # Process progress updates while translation runs
                while not translation_task.done():
                    try:
                        current, total, message = await asyncio.wait_for(
                            progress_queue.get(),
                            timeout=0.5
                        )
                        if progress_callback:
                            await progress_callback(
                                current,
                                total,
                                message,
                                lang,
                                lang_progress=current / total if total > 0 else 0,
                            )
                    except asyncio.TimeoutError:
                        continue

                # Get results
                results, stats = await translation_task

                # Update xcstrings with translations
                for result in results:
                    if result.success and result.key in xcstrings.strings:
                        xcstrings.strings[result.key].set_translation(lang, result.translation, "translated")

                # Store stats
                stats_by_language[lang] = {
                    "total": stats.total,
                    "deepl_count": stats.deepl_count,
                    "gpt4_count": stats.gpt4_count,
                    "failed_count": stats.failed_count,
                    "green_count": stats.green_count,
                    "yellow_count": stats.yellow_count,
                    "red_count": stats.red_count,
                }

                if progress_callback:
                    await progress_callback(
                        lang_idx + 1,
                        total_languages,
                        f"Completed {lang}",
                        lang,
                        stats=stats_by_language[lang],
                    )

            # Convert back to JSON
            output = self.writer.to_string(xcstrings)

            return output, TranslationJobResult(
                success=True,
                languages_processed=list(stats_by_language.keys()),
                stats_by_language=stats_by_language,
            )

        except Exception as e:
            return file_content, TranslationJobResult(
                success=False,
                languages_processed=[],
                stats_by_language={},
                error=str(e),
            )

    async def verify_translations(
        self,
        file_content: str,
        language: str,
        offset: int = 0,
        include_reviewed: bool = False,
        progress_callback: Optional[Callable] = None,
        review_history: Optional["ReviewHistoryService"] = None,
        file_id: Optional[str] = None,
    ) -> tuple[VerificationJobResult, str]:
        """
        Verify translations using LLM semantic review.

        Reviews translations in fixed batches of 100. By default, only reviews
        unreviewed translations. Pass include_reviewed=True to re-check all.

        Args:
            file_content: JSON content of the .xcstrings file
            language: Language code to verify
            offset: Starting offset for pagination (skip this many items)
            include_reviewed: If True, also review already-reviewed strings
            progress_callback: Async callback(current, total, message, language)
            review_history: Optional ReviewHistoryService to skip unchanged translations
            file_id: File ID (required if review_history is provided)

        Returns:
            Tuple of (VerificationJobResult, updated_file_content)
            The updated content has passed strings marked as "reviewed"
        """
        BATCH_SIZE = 100  # Fixed batch size

        try:
            # Parse the file
            xcstrings = self.parser.parse_string(file_content)

            # Collect translations to review
            all_to_review = []
            for key, entry in xcstrings.strings.items():
                if not entry.has_translation(language):
                    continue

                loc = entry.localizations.get(language)
                if not loc or not loc.string_unit:
                    continue

                state = loc.string_unit.state
                translation = loc.string_unit.value
                source = entry.get_source_value(xcstrings.source_language)

                # Include based on include_reviewed flag
                if include_reviewed or state != "reviewed":
                    all_to_review.append({
                        "key": key,
                        "source": source,
                        "translation": translation,
                        "state": state,
                    })

            total_to_review = len(all_to_review)

            # Apply offset and get batch of 100
            translations_batch = all_to_review[offset:offset + BATCH_SIZE]
            has_more = (offset + BATCH_SIZE) < total_to_review
            next_offset = offset + len(translations_batch)

            if not translations_batch:
                return VerificationJobResult(
                    success=True,
                    total_reviewed=0,
                    passed=0,
                    needs_attention=0,
                    issues=[],
                    has_more=False,
                    total_unreviewed=total_to_review,
                    next_offset=offset,
                ), file_content  # Return unchanged content

            # Filter out unchanged translations if review history is available
            skipped_unchanged = 0
            translations_to_review = []

            for t in translations_batch:
                if review_history and file_id:
                    if review_history.is_unchanged(file_id, language, t["key"], t["source"], t["translation"]):
                        skipped_unchanged += 1
                        continue
                translations_to_review.append(t)

            # If all translations were skipped, return early
            if not translations_to_review:
                return VerificationJobResult(
                    success=True,
                    total_reviewed=0,
                    passed=0,
                    needs_attention=0,
                    issues=[],
                    has_more=has_more,
                    total_unreviewed=total_to_review,
                    next_offset=next_offset,
                    skipped_unchanged=skipped_unchanged,
                ), file_content

            # Create reviewer
            reviewer = LLMReviewer()
            batch_size = config.llm_bulk_review_batch_size

            # Create sync progress callback for bulk review
            progress_queue = asyncio.Queue()

            def sync_bulk_progress(current_batch: int, total_batches: int, message: str):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            progress_queue.put((current_batch, total_batches, message)),
                            loop
                        )
                except Exception:
                    pass

            # Run bulk review in thread pool
            async def run_bulk_review():
                return await asyncio.to_thread(
                    reviewer.review_batch_bulk,
                    translations_to_review,
                    language,
                    batch_size,
                    sync_bulk_progress,
                )

            # Start review task
            review_task = asyncio.create_task(run_bulk_review())

            # Process progress updates
            while not review_task.done():
                try:
                    current_batch, total_batches, message = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=0.5
                    )
                    if progress_callback:
                        await progress_callback(
                            current_batch,
                            total_batches,
                            message,
                            language
                        )
                except asyncio.TimeoutError:
                    continue

            # Get bulk review results
            bulk_result: BulkReviewResult = await review_task

            # Convert BulkReviewResult to VerificationJobResult format
            issues = []
            flagged_keys = set()
            for item in bulk_result.items:
                issues.append({
                    "key": item.key,
                    "source": item.source,
                    "translation": item.translation,
                    "issues": item.issues,
                    "suggested_fix": item.suggested_fix,
                })
                flagged_keys.add(item.key)

            # Auto-mark passed strings as "reviewed"
            # Passed = all reviewed keys that weren't flagged with issues
            reviewed_keys = {t["key"] for t in translations_to_review}
            passed_keys = reviewed_keys - flagged_keys
            auto_reviewed_count = 0

            for key in passed_keys:
                if key in xcstrings.strings:
                    loc = xcstrings.strings[key].localizations.get(language)
                    if loc and loc.string_unit:
                        # Only update if not already reviewed
                        if loc.string_unit.state != "reviewed":
                            xcstrings.strings[key].set_translation(
                                language,
                                loc.string_unit.value,
                                "reviewed"
                            )
                            auto_reviewed_count += 1

            # Record review results to history
            if review_history and file_id:
                # Record passed translations
                for t in translations_to_review:
                    key = t["key"]
                    passed = key not in flagged_keys
                    item_issues = []
                    if not passed:
                        # Find issues for this key
                        for issue in issues:
                            if issue["key"] == key:
                                item_issues = issue.get("issues", [])
                                break
                    review_history.record_review(
                        file_id, language, key,
                        t["source"], t["translation"],
                        passed=passed,
                        issues=item_issues,
                    )

            # Convert back to JSON with updated states
            updated_content = self.writer.to_string(xcstrings)

            return VerificationJobResult(
                success=True,
                total_reviewed=bulk_result.total_reviewed,
                passed=bulk_result.passed,
                needs_attention=bulk_result.needs_attention,
                issues=issues,
                has_more=has_more,
                total_unreviewed=total_to_review,
                next_offset=next_offset,
                auto_reviewed_count=auto_reviewed_count,
                skipped_unchanged=skipped_unchanged,
            ), updated_content

        except Exception as e:
            return VerificationJobResult(
                success=False,
                total_reviewed=0,
                passed=0,
                needs_attention=0,
                issues=[],
                error=str(e),
            ), file_content  # Return unchanged on error

    def get_file_stats(self, file_content: str) -> dict:
        """Get statistics for an xcstrings file."""
        xcstrings = self.parser.parse_string(file_content)

        total = len(xcstrings.strings)
        translatable = xcstrings.get_translatable_strings()

        # Get all languages present
        languages = set()
        for entry in xcstrings.strings.values():
            languages.update(entry.localizations.keys())

        # Calculate coverage per language
        coverage = {}
        for lang in sorted(languages):
            if lang == xcstrings.source_language:
                continue
            translated = sum(
                1 for entry in xcstrings.strings.values()
                if entry.has_translation(lang)
            )
            coverage[lang] = {
                "translated": translated,
                "total": len(translatable),
                "percentage": round((translated / len(translatable)) * 100, 1) if translatable else 0,
            }

        return {
            "total_strings": total,
            "translatable_strings": len(translatable),
            "source_language": xcstrings.source_language,
            "languages": sorted(languages),
            "coverage": coverage,
        }

    def get_translations_for_review(
        self,
        file_content: str,
        language: str,
        state_filter: Optional[str] = None,
    ) -> list[dict]:
        """Get translations for a specific language, including untranslated strings."""
        xcstrings = self.parser.parse_string(file_content)
        source_lang = xcstrings.source_language
        translatable = xcstrings.get_translatable_strings()

        translations = []
        for key, entry in xcstrings.strings.items():
            # Skip non-translatable strings
            if key not in translatable:
                continue

            source = entry.get_source_value(source_lang)
            has_translation = entry.has_translation(language)

            if state_filter == "not_translated":
                # Only show untranslated strings
                if has_translation:
                    continue
                translations.append({
                    "key": key,
                    "source": source,
                    "translation": "",
                    "state": "not_translated",
                })
            elif not has_translation:
                # For 'All' filter (None or ""), include untranslated strings
                if state_filter is None or state_filter == "":
                    translations.append({
                        "key": key,
                        "source": source,
                        "translation": "",
                        "state": "not_translated",
                    })
                # For other specific filters (translated, needs_review), skip untranslated
            else:
                # Has translation - apply existing filter logic
                loc = entry.localizations.get(language)
                if not loc or not loc.string_unit:
                    continue

                state = loc.string_unit.state
                # Handle "needs_review" filter to include both needs_review and flagged states
                if state_filter == "needs_review":
                    if state not in ("needs_review", "flagged"):
                        continue
                elif state_filter and state != state_filter:
                    continue

                translations.append({
                    "key": key,
                    "source": source,
                    "translation": loc.string_unit.value,
                    "state": state,
                })

        return translations

    def update_translation(
        self,
        file_content: str,
        language: str,
        key: str,
        new_translation: str,
        new_state: str = "translated",
    ) -> str:
        """Update a single translation and return updated file content."""
        xcstrings = self.parser.parse_string(file_content)

        if key in xcstrings.strings:
            xcstrings.strings[key].set_translation(language, new_translation, new_state)

        return self.writer.to_string(xcstrings)

    def get_untranslated_keys(self, file_content: str, language: str) -> list[dict]:
        """Get untranslated strings for a language."""
        xcstrings = self.parser.parse_string(file_content)

        untranslated = []
        translatable = xcstrings.get_translatable_strings()

        for key in xcstrings.get_untranslated_keys(language):
            if key in translatable:
                untranslated.append({
                    "key": key,
                    "source": translatable[key],
                })

        return untranslated

    def add_language(self, file_content: str, language: str) -> str:
        """
        Add a new language to the xcstrings file.

        Adds a placeholder entry for the first translatable string to register
        the language with Xcode. The entry uses state "new" which Xcode treats
        as needing translation.

        Args:
            file_content: JSON content of the .xcstrings file
            language: Language code to add (e.g., 'ja', 'pt', 'zh-Hans')

        Returns:
            Updated JSON string with the new language added
        """
        xcstrings = self.parser.parse_string(file_content)

        # Check if language already exists
        existing_languages = set()
        for entry in xcstrings.strings.values():
            existing_languages.update(entry.localizations.keys())

        if language in existing_languages:
            raise ValueError(f"Language '{language}' already exists")

        # Add a single placeholder entry to register the language with Xcode
        # We pick the first translatable string and add a "new" state entry
        translatable = xcstrings.get_translatable_strings()
        if translatable:
            first_key = next(iter(translatable))
            if first_key in xcstrings.strings:
                # Use the source value as the initial "translation" with "new" state
                # This marks it as needing translation in Xcode
                source_value = translatable[first_key]
                xcstrings.strings[first_key].set_translation(language, source_value, "new")

        return self.writer.to_string(xcstrings)

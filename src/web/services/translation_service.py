"""Translation service that adapts CLI translation logic for web use."""

import asyncio
from typing import Callable, Optional
from dataclasses import dataclass, asdict

from ...extraction.xcstrings_parser import XCStringsParser
from ...extraction.xcstrings_writer import XCStringsWriter
from ...translation.translator import HybridTranslator, TranslationStats
from ...validation.llm_reviewer import LLMReviewer


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
    avg_semantic_score: float
    avg_fluency_score: float
    issues: list[dict]
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
                        state = "translated" if result.quality_score.category == "green" else "needs_review"
                        xcstrings.strings[result.key].set_translation(lang, result.translation, state)

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
        review_all: bool = False,
        limit: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> VerificationJobResult:
        """
        Verify translations using LLM semantic review.

        Args:
            file_content: JSON content of the .xcstrings file
            language: Language code to verify
            review_all: Review all translations, not just needs_review
            limit: Maximum number of translations to review
            progress_callback: Async callback(current, total, message, language)

        Returns:
            VerificationJobResult
        """
        try:
            # Parse the file
            xcstrings = self.parser.parse_string(file_content)

            # Collect translations to review
            translations_to_review = []
            for key, entry in xcstrings.strings.items():
                if not entry.has_translation(language):
                    continue

                loc = entry.localizations.get(language)
                if not loc or not loc.string_unit:
                    continue

                state = loc.string_unit.state
                translation = loc.string_unit.value
                source = entry.get_source_value(xcstrings.source_language)

                if review_all or state == "needs_review":
                    translations_to_review.append({
                        "key": key,
                        "source": source,
                        "translation": translation,
                        "state": state,
                    })

            if not translations_to_review:
                return VerificationJobResult(
                    success=True,
                    total_reviewed=0,
                    passed=0,
                    needs_attention=0,
                    avg_semantic_score=0,
                    avg_fluency_score=0,
                    issues=[],
                )

            # Apply limit
            if limit:
                translations_to_review = translations_to_review[:limit]

            # Create reviewer
            reviewer = LLMReviewer()

            # Create sync progress callback
            progress_queue = asyncio.Queue()

            def sync_progress(current: int, total: int, key: str):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            progress_queue.put((current, total, key)),
                            loop
                        )
                except Exception:
                    pass

            # Run review in thread pool
            async def run_review():
                return await asyncio.to_thread(
                    reviewer.review_batch,
                    translations_to_review,
                    language,
                    sync_progress,
                )

            # Start review task
            review_task = asyncio.create_task(run_review())

            # Process progress updates
            while not review_task.done():
                try:
                    current, total, key = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=0.5
                    )
                    if progress_callback:
                        await progress_callback(current, total, f"Reviewing: {key}", language)
                except asyncio.TimeoutError:
                    continue

            # Get results
            results = await review_task

            # Calculate stats
            passed = [r for r in results if r.passed]
            needs_attention = [r for r in results if r.needs_attention]

            total = len(results)
            avg_semantic = sum(r.semantic_score for r in results) / total if total else 0
            avg_fluency = sum(r.fluency_score for r in results) / total if total else 0

            # Collect issues
            issues = []
            for r in needs_attention:
                issues.append({
                    "key": r.key,
                    "source": r.source,
                    "translation": r.translation,
                    "semantic_score": r.semantic_score,
                    "fluency_score": r.fluency_score,
                    "overall_score": r.overall_score,
                    "issues": r.issues,
                    "suggested_fix": r.suggested_fix,
                })

            return VerificationJobResult(
                success=True,
                total_reviewed=total,
                passed=len(passed),
                needs_attention=len(needs_attention),
                avg_semantic_score=avg_semantic,
                avg_fluency_score=avg_fluency,
                issues=issues,
            )

        except Exception as e:
            return VerificationJobResult(
                success=False,
                total_reviewed=0,
                passed=0,
                needs_attention=0,
                avg_semantic_score=0,
                avg_fluency_score=0,
                issues=[],
                error=str(e),
            )

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
                if state_filter and state != state_filter:
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

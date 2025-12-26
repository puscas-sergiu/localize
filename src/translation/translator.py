"""Hybrid translator with DeepL primary and GPT-4 fallback."""

from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

from ..models.translation_result import TranslationResult, QualityScore
from ..validation.quality_scorer import QualityScorer
from .clients.deepl_client import DeepLClient
from .clients.openai_client import OpenAIClient
from ..config import config


@dataclass
class TranslationStats:
    """Statistics for a translation batch."""

    total: int = 0
    deepl_count: int = 0
    gpt4_count: int = 0
    failed_count: int = 0
    green_count: int = 0
    yellow_count: int = 0
    red_count: int = 0


class HybridTranslator:
    """
    Hybrid translator that uses DeepL as primary and GPT-4 as fallback.

    Strategy:
    1. Translate with DeepL first (cheaper, faster)
    2. Score the result
    3. If score < threshold, retry with GPT-4
    4. Return best result
    """

    def __init__(
        self,
        deepl_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        quality_threshold: float = 80.0,
        glossary: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        """
        Initialize the hybrid translator.

        Args:
            deepl_api_key: DeepL API key (uses env if not provided)
            openai_api_key: OpenAI API key (uses env if not provided)
            quality_threshold: Score below which GPT-4 fallback is triggered
            glossary: Optional glossary for consistent terminology
        """
        self.deepl = DeepLClient(api_key=deepl_api_key)
        self.openai = OpenAIClient(api_key=openai_api_key)
        self.scorer = QualityScorer(glossary=glossary)
        self.quality_threshold = quality_threshold

    def translate(
        self,
        key: str,
        source: str,
        target_lang: str,
        context: Optional[str] = None,
        force_gpt4: bool = False,
    ) -> TranslationResult:
        """
        Translate a single string.

        Args:
            key: The string key (for tracking)
            source: Source text to translate
            target_lang: Target language code
            context: Optional UI context for better translation
            force_gpt4: If True, skip DeepL and use GPT-4 directly

        Returns:
            TranslationResult with translation and quality score
        """
        # Skip empty or trivial strings
        if not source or not source.strip():
            return TranslationResult(
                key=key,
                source=source,
                translation=source,
                target_lang=target_lang,
                quality_score=QualityScore(
                    overall=100,
                    placeholder_score=100,
                    glossary_score=100,
                    length_score=100,
                    format_score=100,
                    category="green",
                    issues=[],
                ),
                provider="skip",
                fallback_used=False,
            )

        # Skip strings that are just placeholders or symbols
        if self._is_non_translatable(source):
            return TranslationResult(
                key=key,
                source=source,
                translation=source,
                target_lang=target_lang,
                quality_score=QualityScore(
                    overall=100,
                    placeholder_score=100,
                    glossary_score=100,
                    length_score=100,
                    format_score=100,
                    category="green",
                    issues=[],
                ),
                provider="skip",
                fallback_used=False,
            )

        fallback_used = False
        provider = "deepl"

        try:
            if not force_gpt4:
                # Try DeepL first
                deepl_result = self.deepl.translate(
                    text=source,
                    target_lang=target_lang,
                )
                translation = deepl_result.text
                quality = self.scorer.score(source, translation, target_lang)

                # Check if quality meets threshold
                if quality.overall < self.quality_threshold or quality.category == "red":
                    fallback_used = True
                    # Fall back to GPT-4
                    translation = self.openai.translate(
                        text=source,
                        target_lang=target_lang,
                        context=context,
                    )
                    quality = self.scorer.score(source, translation, target_lang)
                    provider = "gpt4"
            else:
                # Force GPT-4
                translation = self.openai.translate(
                    text=source,
                    target_lang=target_lang,
                    context=context,
                )
                quality = self.scorer.score(source, translation, target_lang)
                provider = "gpt4"

            return TranslationResult(
                key=key,
                source=source,
                translation=translation,
                target_lang=target_lang,
                quality_score=quality,
                provider=provider,
                fallback_used=fallback_used,
            )

        except Exception as e:
            # Return error result
            return TranslationResult(
                key=key,
                source=source,
                translation="",
                target_lang=target_lang,
                quality_score=QualityScore(
                    overall=0,
                    placeholder_score=0,
                    glossary_score=0,
                    length_score=0,
                    format_score=0,
                    category="red",
                    issues=[str(e)],
                ),
                provider=provider,
                fallback_used=fallback_used,
                error=str(e),
            )

    def translate_batch(
        self,
        strings: Dict[str, str],
        target_lang: str,
        context: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> tuple[List[TranslationResult], TranslationStats]:
        """
        Translate a batch of strings using batched API calls.

        Args:
            strings: Dictionary of {key: source_text}
            target_lang: Target language code
            context: Optional shared context for translations
            progress_callback: Optional callback(current, total, status_message) for progress updates

        Returns:
            Tuple of (list of results, statistics)
        """
        results: Dict[str, TranslationResult] = {}
        stats = TranslationStats(total=len(strings))

        # Step 1: Separate translatable from non-translatable
        translatable: Dict[str, str] = {}
        for key, source in strings.items():
            if not source or not source.strip() or self._is_non_translatable(source):
                # Skip non-translatable strings
                results[key] = self._create_skip_result(key, source, target_lang)
            else:
                translatable[key] = source

        if not translatable:
            return list(results.values()), stats

        # Step 2: Batch DeepL translation
        if progress_callback:
            progress_callback(0, len(strings), "Translating with DeepL...")

        deepl_results = self._batch_translate_deepl(
            translatable, target_lang, progress_callback, len(strings)
        )

        # Step 3: Score DeepL results and identify fallbacks needed
        if progress_callback:
            progress_callback(len(deepl_results), len(strings), "Scoring translations...")

        fallback_needed: Dict[str, str] = {}
        for key, (source, translation) in deepl_results.items():
            # Empty translation means DeepL failed, needs fallback
            if not translation:
                fallback_needed[key] = source
                continue

            quality = self.scorer.score(source, translation, target_lang)

            if quality.overall < self.quality_threshold or quality.category == "red":
                fallback_needed[key] = source
            else:
                results[key] = TranslationResult(
                    key=key,
                    source=source,
                    translation=translation,
                    target_lang=target_lang,
                    quality_score=quality,
                    provider="deepl",
                    fallback_used=False,
                )
                stats.deepl_count += 1
                self._update_quality_stats(stats, quality)

        # Step 4: Batch OpenAI fallback for low-quality results
        if fallback_needed:
            if progress_callback:
                progress_callback(
                    len(results), len(strings),
                    f"Re-translating {len(fallback_needed)} strings with GPT-4..."
                )

            openai_results = self._batch_translate_openai(
                fallback_needed, target_lang, context, progress_callback, len(strings)
            )

            for key, (source, translation) in openai_results.items():
                if translation:
                    quality = self.scorer.score(source, translation, target_lang)
                    results[key] = TranslationResult(
                        key=key,
                        source=source,
                        translation=translation,
                        target_lang=target_lang,
                        quality_score=quality,
                        provider="gpt4",
                        fallback_used=True,
                    )
                    stats.gpt4_count += 1
                    self._update_quality_stats(stats, quality)
                else:
                    # Both DeepL and OpenAI failed
                    stats.failed_count += 1
                    results[key] = self._create_error_result(
                        key, source, target_lang, "Translation failed"
                    )

        # Step 5: Handle any remaining errors
        for key in translatable:
            if key not in results:
                stats.failed_count += 1
                results[key] = self._create_error_result(
                    key, translatable[key], target_lang, "Translation failed"
                )

        # Return in original order
        ordered_results = [results[key] for key in strings.keys()]
        return ordered_results, stats

    def _batch_translate_deepl(
        self,
        strings: Dict[str, str],
        target_lang: str,
        progress_callback: Optional[Callable],
        total_count: int,
    ) -> Dict[str, tuple[str, str]]:
        """
        Batch translate using DeepL API.

        Returns:
            Dict of {key: (source, translation)}
        """
        results = {}
        keys = list(strings.keys())
        texts = list(strings.values())

        batch_size = config.deepl_batch_size

        for i in range(0, len(texts), batch_size):
            batch_keys = keys[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]

            try:
                deepl_results = self.deepl.translate_batch(
                    texts=batch_texts,
                    target_lang=target_lang,
                )

                for key, text, result in zip(batch_keys, batch_texts, deepl_results):
                    results[key] = (text, result.text)

            except Exception:
                # On batch failure, mark all as needing fallback (empty translation)
                for key, text in zip(batch_keys, batch_texts):
                    results[key] = (text, "")

            if progress_callback:
                completed = min(i + batch_size, len(texts))
                progress_callback(completed, total_count, f"DeepL: {completed}/{len(texts)}")

        return results

    def _batch_translate_openai(
        self,
        strings: Dict[str, str],
        target_lang: str,
        context: Optional[str],
        progress_callback: Optional[Callable],
        total_count: int,
    ) -> Dict[str, tuple[str, str]]:
        """
        Batch translate using OpenAI API with JSON format.

        Returns:
            Dict of {key: (source, translation)}
        """
        results = {}
        keys = list(strings.keys())
        texts = list(strings.values())

        batch_size = config.openai_batch_size

        for i in range(0, len(texts), batch_size):
            batch_keys = keys[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]

            try:
                translations = self.openai.translate_batch(
                    texts=batch_texts,
                    target_lang=target_lang,
                    context=context,
                )

                for key, text, translation in zip(batch_keys, batch_texts, translations):
                    results[key] = (text, translation)

            except Exception:
                # On batch failure, try individual translations as final fallback
                for key, text in zip(batch_keys, batch_texts):
                    try:
                        translation = self.openai.translate(
                            text=text,
                            target_lang=target_lang,
                            context=context,
                        )
                        results[key] = (text, translation)
                    except Exception:
                        results[key] = (text, "")

            if progress_callback:
                completed = min(i + batch_size, len(texts))
                progress_callback(
                    len(strings) - len(keys) + completed,
                    total_count,
                    f"GPT-4: {completed}/{len(texts)}"
                )

        return results

    def _update_quality_stats(self, stats: TranslationStats, quality: QualityScore):
        """Update stats based on quality category."""
        if quality.category == "green":
            stats.green_count += 1
        elif quality.category == "yellow":
            stats.yellow_count += 1
        else:
            stats.red_count += 1

    def _create_skip_result(
        self, key: str, source: str, target_lang: str
    ) -> TranslationResult:
        """Create a result for skipped (non-translatable) strings."""
        return TranslationResult(
            key=key,
            source=source,
            translation=source,
            target_lang=target_lang,
            quality_score=QualityScore(
                overall=100,
                placeholder_score=100,
                glossary_score=100,
                length_score=100,
                format_score=100,
                category="green",
                issues=[],
            ),
            provider="skip",
            fallback_used=False,
        )

    def _create_error_result(
        self, key: str, source: str, target_lang: str, error: str
    ) -> TranslationResult:
        """Create a result for failed translations."""
        return TranslationResult(
            key=key,
            source=source,
            translation="",
            target_lang=target_lang,
            quality_score=QualityScore(
                overall=0,
                placeholder_score=0,
                glossary_score=0,
                length_score=0,
                format_score=0,
                category="red",
                issues=[error],
            ),
            provider="error",
            fallback_used=False,
            error=error,
        )

    def _is_non_translatable(self, text: str) -> bool:
        """Check if text should be skipped (symbols, numbers only, etc.)."""
        # Strip whitespace
        stripped = text.strip()

        # Empty strings
        if not stripped:
            return True

        # Single characters that are symbols
        if len(stripped) == 1 and not stripped.isalpha():
            return True

        # Pure numbers or percentages
        if stripped.replace(".", "").replace(",", "").replace("%", "").isdigit():
            return True

        # File extensions
        if stripped.startswith(".") and len(stripped) <= 5:
            return True

        # URLs
        if stripped.startswith(("http://", "https://", "www.")):
            return True

        # Email addresses
        if "@" in stripped and "." in stripped and " " not in stripped:
            return True

        # Placeholders only (e.g., "%@", "%lld")
        import re
        placeholder_only = re.fullmatch(r"[%@dlfs\d$\s\-/]+", stripped)
        if placeholder_only:
            return True

        return False

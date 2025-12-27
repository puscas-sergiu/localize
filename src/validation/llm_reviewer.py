"""LLM-based semantic quality reviewer for translations."""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from openai import OpenAI

from ..config import config


@dataclass
class ReviewResult:
    """Result of LLM semantic review for a single translation."""

    key: str
    source: str
    translation: str
    language: str
    semantic_score: float  # 0-100: Does it convey the same meaning?
    fluency_score: float  # 0-100: Is it grammatically correct and natural?
    issues: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None

    @property
    def overall_score(self) -> float:
        """Combined score (weighted average)."""
        return (self.semantic_score * 0.7) + (self.fluency_score * 0.3)

    @property
    def passed(self) -> bool:
        """Check if the review passed (no major issues)."""
        return self.overall_score >= 80 and self.semantic_score >= 70

    @property
    def needs_attention(self) -> bool:
        """Check if the translation needs human attention."""
        return not self.passed or len(self.issues) > 0


@dataclass
class ReviewWithSuggestionsResult:
    """Result of LLM review with multiple translation suggestions."""

    key: str
    source: str
    translation: str
    language: str
    issues: List[str] = field(default_factory=list)
    suggestions: List[Dict[str, str]] = field(default_factory=list)  # [{"text": "...", "explanation": "..."}]


class LLMReviewer:
    """Uses GPT to semantically review translations."""

    LANGUAGE_NAMES = {
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "es": "Spanish",
        "ro": "Romanian",
        "en": "English",
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM reviewer.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY from environment.
        """
        self.api_key = api_key or config.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key is required for LLM review")
        self.client = OpenAI(api_key=self.api_key)
        self.model = config.openai_model
        self.temperature = 0.2  # Lower temperature for more consistent evaluation

    def review(
        self,
        source: str,
        translation: str,
        target_lang: str,
        key: str = "",
        context: Optional[str] = None,
    ) -> ReviewResult:
        """
        Review a single translation for semantic accuracy and fluency.

        Args:
            source: Original English text
            translation: Translated text
            target_lang: Target language code (e.g., "de", "fr")
            key: String key for reference
            context: Optional context about where the string is used

        Returns:
            ReviewResult with scores and issues
        """
        lang_name = self.LANGUAGE_NAMES.get(target_lang.lower(), target_lang)

        system_prompt = self._build_system_prompt(lang_name)
        user_prompt = self._build_user_prompt(source, translation, lang_name, context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content.strip()
            result_data = json.loads(result_text)

            return ReviewResult(
                key=key,
                source=source,
                translation=translation,
                language=target_lang,
                semantic_score=float(result_data.get("semantic_score", 0)),
                fluency_score=float(result_data.get("fluency_score", 0)),
                issues=result_data.get("issues", []),
                suggested_fix=result_data.get("suggested_fix"),
            )

        except Exception as e:
            # Return a result indicating review failed
            return ReviewResult(
                key=key,
                source=source,
                translation=translation,
                language=target_lang,
                semantic_score=0,
                fluency_score=0,
                issues=[f"Review failed: {str(e)}"],
                suggested_fix=None,
            )

    def review_batch(
        self,
        translations: List[Dict[str, str]],
        target_lang: str,
        progress_callback=None,
    ) -> List[ReviewResult]:
        """
        Review multiple translations.

        Args:
            translations: List of dicts with 'key', 'source', 'translation' keys
            target_lang: Target language code
            progress_callback: Optional callback(current, total, key) for progress updates

        Returns:
            List of ReviewResult objects
        """
        results = []
        total = len(translations)

        for i, item in enumerate(translations):
            if progress_callback:
                progress_callback(i + 1, total, item.get("key", ""))

            result = self.review(
                source=item["source"],
                translation=item["translation"],
                target_lang=target_lang,
                key=item.get("key", ""),
                context=item.get("context"),
            )
            results.append(result)

        return results

    def _build_system_prompt(self, lang_name: str) -> str:
        """Build the system prompt for review."""
        return f"""You are an expert translator and quality reviewer for {lang_name} translations in a mobile app context.

Your task is to evaluate a translation and provide:
1. A semantic accuracy score (0-100): Does the translation convey the exact same meaning as the source?
2. A fluency score (0-100): Is the translation grammatically correct and natural-sounding in {lang_name}?
3. A list of specific issues found (empty if none)
4. A suggested fix if there are issues (null if translation is good)

IMPORTANT GUIDELINES:
- Focus on meaning preservation - minor phrasing differences are OK if meaning is preserved
- Consider mobile UI context - translations should be concise
- iOS format specifiers (%@, %d, %1$@, etc.) should be preserved but their position can change
- Be strict about semantic errors (wrong meaning, omissions, additions)
- Be lenient about stylistic differences

RESPONSE FORMAT (JSON only):
{{
  "semantic_score": <0-100>,
  "fluency_score": <0-100>,
  "issues": ["issue 1", "issue 2"],
  "suggested_fix": "<corrected translation or null>"
}}

Score guidelines:
- 95-100: Perfect or near-perfect translation
- 80-94: Good translation with minor issues
- 60-79: Acceptable but needs improvement
- Below 60: Significant problems, needs retranslation"""

    def _build_user_prompt(
        self,
        source: str,
        translation: str,
        lang_name: str,
        context: Optional[str],
    ) -> str:
        """Build the user prompt for review."""
        prompt = f"""Review this English to {lang_name} translation:

SOURCE (English):
{source}

TRANSLATION ({lang_name}):
{translation}"""

        if context:
            prompt += f"\n\nCONTEXT: {context}"

        prompt += "\n\nProvide your evaluation as JSON."

        return prompt

    def review_with_suggestions(
        self,
        source: str,
        translation: str,
        target_lang: str,
        key: str = "",
        context: Optional[str] = None,
        num_suggestions: int = 3,
    ) -> ReviewWithSuggestionsResult:
        """
        Review a translation and provide multiple alternative suggestions.

        Args:
            source: Original English text
            translation: Current translated text
            target_lang: Target language code (e.g., "de", "fr")
            key: String key for reference
            context: Optional context about where the string is used
            num_suggestions: Number of suggestions to generate (default 3)

        Returns:
            ReviewWithSuggestionsResult with issues and ranked suggestions
        """
        lang_name = self.LANGUAGE_NAMES.get(target_lang.lower(), target_lang)

        system_prompt = self._build_suggestions_system_prompt(lang_name, num_suggestions)
        user_prompt = self._build_suggestions_user_prompt(source, translation, lang_name, context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content.strip()
            result_data = json.loads(result_text)

            return ReviewWithSuggestionsResult(
                key=key,
                source=source,
                translation=translation,
                language=target_lang,
                issues=result_data.get("issues", []),
                suggestions=result_data.get("suggestions", []),
            )

        except Exception as e:
            # Return a result indicating review failed
            return ReviewWithSuggestionsResult(
                key=key,
                source=source,
                translation=translation,
                language=target_lang,
                issues=[f"Review failed: {str(e)}"],
                suggestions=[],
            )

    def _build_suggestions_system_prompt(self, lang_name: str, num_suggestions: int) -> str:
        """Build the system prompt for review with suggestions."""
        return f"""You are an expert translator and quality reviewer for {lang_name} translations in a mobile app context.

Your task is to:
1. Identify any issues with the translation (empty list if none)
2. Provide {num_suggestions} alternative translation suggestions ranked by quality

IMPORTANT GUIDELINES:
- Focus on meaning preservation and natural phrasing
- Consider mobile UI context - translations should be concise
- iOS format specifiers (%@, %d, %1$@, etc.) MUST be preserved exactly
- If the translation is already perfect, still provide alternative phrasings for variety
- The first suggestion should be your best/recommended option

RESPONSE FORMAT (JSON only):
{{
  "issues": ["issue 1", "issue 2"],
  "suggestions": [
    {{"text": "<best translation>", "explanation": "<brief reason>"}},
    {{"text": "<alternative 1>", "explanation": "<brief reason>"}},
    {{"text": "<alternative 2>", "explanation": "<brief reason>"}}
  ]
}}"""

    def _build_suggestions_user_prompt(
        self,
        source: str,
        translation: str,
        lang_name: str,
        context: Optional[str],
    ) -> str:
        """Build the user prompt for review with suggestions."""
        prompt = f"""Review this English to {lang_name} translation and provide alternatives:

SOURCE (English):
{source}

CURRENT TRANSLATION ({lang_name}):
{translation}"""

        if context:
            prompt += f"\n\nCONTEXT: {context}"

        prompt += "\n\nProvide your review and suggestions as JSON."

        return prompt

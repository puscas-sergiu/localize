"""Quality scoring system for translations."""

from typing import List, Dict, Optional, Tuple

from ..models.translation_result import QualityScore
from .placeholder_validator import PlaceholderValidator


class QualityScorer:
    """
    Scores translation quality based on multiple factors.

    Scoring weights:
    - Placeholder validation: 40% (CRITICAL)
    - Glossary compliance: 25%
    - Length appropriateness: 20%
    - Format preservation: 15%

    Categories:
    - Green (95+): Auto-approve
    - Yellow (80-94): Needs review
    - Red (<80): Failed, needs retry or human intervention
    """

    def __init__(self, glossary: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Initialize the quality scorer.

        Args:
            glossary: Optional multi-language glossary.
                     Format: {source_term: {lang_code: translation}}
        """
        self.glossary = glossary or {}
        self.placeholder_validator = PlaceholderValidator()

    def score(
        self,
        source: str,
        translation: str,
        target_lang: str,
        max_length_ratio: float = 1.5,
        required_glossary_terms: Optional[List[str]] = None,
    ) -> QualityScore:
        """
        Score a translation's quality.

        Args:
            source: Original source text
            translation: Translated text
            target_lang: Target language code
            max_length_ratio: Maximum acceptable translation/source length ratio
            required_glossary_terms: List of terms that must use glossary translations

        Returns:
            QualityScore with detailed breakdown
        """
        issues = []

        # 1. Placeholder validation (40% weight) - CRITICAL
        placeholder_score, ph_issues = self._score_placeholders(source, translation)
        issues.extend(ph_issues)

        # 2. Glossary compliance (25% weight)
        glossary_score, gl_issues = self._score_glossary(
            source, translation, target_lang, required_glossary_terms
        )
        issues.extend(gl_issues)

        # 3. Length appropriateness (20% weight)
        length_score, len_issues = self._score_length(source, translation, max_length_ratio)
        issues.extend(len_issues)

        # 4. Format preservation (15% weight)
        format_score, fmt_issues = self._score_format(source, translation)
        issues.extend(fmt_issues)

        # Calculate weighted overall score
        overall = (
            placeholder_score * 0.40
            + glossary_score * 0.25
            + length_score * 0.20
            + format_score * 0.15
        )

        # Determine category
        # Placeholder errors always result in red, regardless of overall score
        if placeholder_score < 100:
            category = "red"
        elif overall >= 95:
            category = "green"
        elif overall >= 80:
            category = "yellow"
        else:
            category = "red"

        return QualityScore(
            overall=round(overall, 2),
            placeholder_score=placeholder_score,
            glossary_score=glossary_score,
            length_score=length_score,
            format_score=format_score,
            category=category,
            issues=issues,
        )

    def _score_placeholders(
        self, source: str, translation: str
    ) -> Tuple[float, List[str]]:
        """Score placeholder preservation."""
        is_valid, issues = self.placeholder_validator.validate(source, translation)

        if is_valid and not issues:
            return 100.0, []

        # Any critical issue = 0 score
        critical_issues = [i for i in issues if i.severity == "critical"]
        if critical_issues:
            return 0.0, [i.message for i in issues]

        # Warnings reduce score but don't fail
        warning_count = len([i for i in issues if i.severity == "warning"])
        score = max(0, 100 - (warning_count * 20))

        return score, [i.message for i in issues]

    def _score_glossary(
        self,
        source: str,
        translation: str,
        target_lang: str,
        required_terms: Optional[List[str]],
    ) -> Tuple[float, List[str]]:
        """Score glossary term compliance."""
        if not required_terms or target_lang not in self._get_supported_glossary_langs():
            return 100.0, []

        issues = []
        matched = 0
        total_required = 0

        source_lower = source.lower()
        translation_lower = translation.lower()

        for term in required_terms:
            if term.lower() in source_lower:
                total_required += 1
                expected = self._get_glossary_translation(term, target_lang)

                if expected and expected.lower() in translation_lower:
                    matched += 1
                elif expected:
                    issues.append(
                        f"Glossary term '{term}' should be translated as '{expected}'"
                    )

        if total_required == 0:
            return 100.0, []

        score = (matched / total_required) * 100
        return score, issues

    def _score_length(
        self, source: str, translation: str, max_ratio: float
    ) -> Tuple[float, List[str]]:
        """Score translation length appropriateness."""
        if not source or not translation:
            return 100.0, []

        ratio = len(translation) / len(source)

        if ratio <= max_ratio:
            return 100.0, []
        elif ratio <= max_ratio * 1.25:
            return 80.0, [f"Translation is {ratio:.1f}x longer than source"]
        elif ratio <= max_ratio * 1.5:
            return 60.0, [f"Translation is significantly longer ({ratio:.1f}x)"]
        else:
            return 40.0, [f"Translation is too long ({ratio:.1f}x source length)"]

    def _score_format(self, source: str, translation: str) -> Tuple[float, List[str]]:
        """Score format preservation (whitespace, newlines, etc.)."""
        issues = []
        score = 100.0

        # Check newline preservation
        source_newlines = source.count("\n")
        trans_newlines = translation.count("\n")
        if source_newlines != trans_newlines:
            score -= 20
            issues.append(
                f"Newline count changed: {source_newlines} → {trans_newlines}"
            )

        # Check leading whitespace
        if source.startswith(" ") != translation.startswith(" "):
            score -= 10
            issues.append("Leading whitespace changed")

        # Check trailing whitespace
        if source.endswith(" ") != translation.endswith(" "):
            score -= 10
            issues.append("Trailing whitespace changed")

        # Check for double spaces (common translation artifact)
        if "  " not in source and "  " in translation:
            score -= 5
            issues.append("Double spaces introduced")

        return max(0, score), issues

    def _get_supported_glossary_langs(self) -> List[str]:
        """Get list of languages with glossary entries."""
        langs = set()
        for translations in self.glossary.values():
            if isinstance(translations, dict):
                langs.update(translations.keys())
        return list(langs)

    def _get_glossary_translation(
        self, term: str, target_lang: str
    ) -> Optional[str]:
        """Get the glossary translation for a term."""
        term_entry = self.glossary.get(term) or self.glossary.get(term.lower())
        if term_entry and isinstance(term_entry, dict):
            return term_entry.get(target_lang)
        return None

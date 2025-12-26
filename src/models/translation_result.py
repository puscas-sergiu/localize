"""Data models for translation results and quality scoring."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class QualityScore:
    """Represents the quality assessment of a translation."""

    overall: float  # 0-100
    placeholder_score: float  # 0-100
    glossary_score: float  # 0-100
    length_score: float  # 0-100
    format_score: float  # 0-100
    category: str  # "green", "yellow", "red"
    issues: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if the translation passed quality checks."""
        return self.category in ("green", "yellow")

    @property
    def needs_review(self) -> bool:
        """Check if the translation needs human review."""
        return self.category == "yellow"

    @property
    def failed(self) -> bool:
        """Check if the translation failed quality checks."""
        return self.category == "red"


@dataclass
class TranslationResult:
    """Represents the result of translating a single string."""

    key: str
    source: str
    translation: str
    target_lang: str
    quality_score: QualityScore
    provider: str  # "deepl" or "gpt4"
    fallback_used: bool = False
    cached: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if translation was successful."""
        return self.error is None and self.translation != ""

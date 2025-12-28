"""Data models for XCStrings file structure."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class StringUnit:
    """Represents a single string translation unit."""

    value: str
    state: str = "new"  # new, translated, needs_review, reviewed, flagged, stale


@dataclass
class Localization:
    """Represents a localization entry for a specific language."""

    string_unit: Optional[StringUnit] = None
    variations: Optional[Dict[str, Any]] = None  # For plurals/device variants


@dataclass
class StringEntry:
    """Represents a single localizable string entry."""

    key: str
    comment: Optional[str] = None
    localizations: Dict[str, Localization] = field(default_factory=dict)
    extraction_state: Optional[str] = None  # manual, extracted_with_value

    def get_source_value(self, source_language: str = "en") -> str:
        """Get the source language value for this string."""
        if source_language in self.localizations:
            loc = self.localizations[source_language]
            if loc.string_unit:
                return loc.string_unit.value
        # If no explicit localization, the key itself is often the source value
        return self.key

    def has_translation(self, language: str) -> bool:
        """Check if this string has a translation for the given language."""
        if language not in self.localizations:
            return False
        loc = self.localizations[language]
        return loc.string_unit is not None and loc.string_unit.value != ""

    def set_translation(self, language: str, value: str, state: str = "translated") -> None:
        """Set a translation for the given language."""
        self.localizations[language] = Localization(
            string_unit=StringUnit(value=value, state=state)
        )


@dataclass
class XCStringsFile:
    """Represents a complete .xcstrings file."""

    source_language: str
    strings: Dict[str, StringEntry]
    version: str = "1.0"

    def get_untranslated_keys(self, target_language: str) -> list:
        """Get list of keys that don't have translations for the target language."""
        untranslated = []
        for key, entry in self.strings.items():
            if not entry.has_translation(target_language):
                untranslated.append(key)
        return untranslated

    def get_translatable_strings(self) -> Dict[str, str]:
        """Get all strings that need translation (key -> source value)."""
        result = {}
        for key, entry in self.strings.items():
            source_value = entry.get_source_value(self.source_language)
            # Skip empty strings or single characters that don't need translation
            if source_value and len(source_value.strip()) > 0:
                result[key] = source_value
        return result

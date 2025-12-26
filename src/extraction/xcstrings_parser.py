"""Parser for Apple's .xcstrings JSON format (Xcode 15+)."""

import json
from typing import Dict, Any
from pathlib import Path

from ..models.string_entry import StringUnit, Localization, StringEntry, XCStringsFile


class XCStringsParser:
    """Parser for .xcstrings files."""

    def parse(self, file_path: str) -> XCStringsFile:
        """
        Parse an .xcstrings file and return a structured representation.

        Args:
            file_path: Path to the .xcstrings file

        Returns:
            XCStringsFile object containing all parsed data
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path.suffix == ".xcstrings":
            raise ValueError(f"Expected .xcstrings file, got: {path.suffix}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._parse_data(data)

    def parse_string(self, content: str) -> XCStringsFile:
        """
        Parse .xcstrings content from a string.

        Args:
            content: JSON string content

        Returns:
            XCStringsFile object
        """
        data = json.loads(content)
        return self._parse_data(data)

    def _parse_data(self, data: Dict[str, Any]) -> XCStringsFile:
        """Parse the JSON data structure into our model."""
        source_language = data.get("sourceLanguage", "en")
        version = data.get("version", "1.0")
        strings = {}

        for key, entry_data in data.get("strings", {}).items():
            strings[key] = self._parse_string_entry(key, entry_data)

        return XCStringsFile(
            source_language=source_language,
            strings=strings,
            version=version,
        )

    def _parse_string_entry(self, key: str, entry_data: Dict[str, Any]) -> StringEntry:
        """Parse a single string entry."""
        comment = entry_data.get("comment")
        extraction_state = entry_data.get("extractionState")
        localizations = {}

        for lang, loc_data in entry_data.get("localizations", {}).items():
            localizations[lang] = self._parse_localization(loc_data)

        return StringEntry(
            key=key,
            comment=comment,
            localizations=localizations,
            extraction_state=extraction_state,
        )

    def _parse_localization(self, loc_data: Dict[str, Any]) -> Localization:
        """Parse a localization entry."""
        string_unit = None
        variations = None

        if "stringUnit" in loc_data:
            su = loc_data["stringUnit"]
            string_unit = StringUnit(
                value=su.get("value", ""),
                state=su.get("state", "new"),
            )

        if "variations" in loc_data:
            variations = loc_data["variations"]

        return Localization(string_unit=string_unit, variations=variations)

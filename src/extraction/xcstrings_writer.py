"""Writer for Apple's .xcstrings JSON format (Xcode 15+)."""

import json
from typing import Dict, Any
from pathlib import Path

from ..models.string_entry import XCStringsFile, StringEntry, Localization


class XCStringsWriter:
    """Writer for .xcstrings files."""

    def write(self, xcstrings: XCStringsFile, output_path: str) -> None:
        """
        Write an XCStringsFile to disk.

        Args:
            xcstrings: The XCStringsFile to write
            output_path: Path to write the file to
        """
        data = self._to_dict(xcstrings)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")  # Trailing newline

    def to_string(self, xcstrings: XCStringsFile) -> str:
        """
        Convert an XCStringsFile to a JSON string.

        Args:
            xcstrings: The XCStringsFile to convert

        Returns:
            JSON string representation
        """
        data = self._to_dict(xcstrings)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _to_dict(self, xcstrings: XCStringsFile) -> Dict[str, Any]:
        """Convert XCStringsFile to dictionary for JSON serialization."""
        # Sort strings by key for consistent output
        sorted_keys = sorted(xcstrings.strings.keys())

        strings_dict = {}
        for key in sorted_keys:
            entry = xcstrings.strings[key]
            strings_dict[key] = self._entry_to_dict(entry)

        return {
            "sourceLanguage": xcstrings.source_language,
            "strings": strings_dict,
            "version": xcstrings.version,
        }

    def _entry_to_dict(self, entry: StringEntry) -> Dict[str, Any]:
        """Convert a StringEntry to dictionary."""
        entry_dict: Dict[str, Any] = {}

        if entry.comment:
            entry_dict["comment"] = entry.comment

        if entry.extraction_state:
            entry_dict["extractionState"] = entry.extraction_state

        if entry.localizations:
            # Sort localizations by language code for consistent output
            sorted_langs = sorted(entry.localizations.keys())
            localizations_dict = {}

            for lang in sorted_langs:
                loc = entry.localizations[lang]
                loc_dict = self._localization_to_dict(loc)
                if loc_dict:  # Only include non-empty localizations
                    localizations_dict[lang] = loc_dict

            if localizations_dict:
                entry_dict["localizations"] = localizations_dict

        return entry_dict

    def _localization_to_dict(self, loc: Localization) -> Dict[str, Any]:
        """Convert a Localization to dictionary."""
        loc_dict: Dict[str, Any] = {}

        if loc.string_unit:
            loc_dict["stringUnit"] = {
                "state": loc.string_unit.state,
                "value": loc.string_unit.value,
            }

        if loc.variations:
            loc_dict["variations"] = loc.variations

        return loc_dict

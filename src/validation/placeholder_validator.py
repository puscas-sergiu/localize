"""Validator for iOS format specifier placeholders."""

import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class PlaceholderIssue:
    """Represents a placeholder validation issue."""

    error_type: str  # missing, extra, mismatch, order_changed
    message: str
    severity: str  # critical, warning


class PlaceholderValidator:
    """
    Validates that iOS format specifiers are preserved in translations.

    iOS format specifiers include:
    - %@ - Object/string
    - %d, %ld, %lld - Integers
    - %f, %.2f - Floats
    - %% - Literal percent
    - %1$@, %2$lld - Positional specifiers
    """

    # Regex pattern for iOS format specifiers
    # Matches: %[-+0 #]*[width][.precision][length]type or %n$type (positional)
    PLACEHOLDER_PATTERN = re.compile(
        r"%"  # Start with %
        r"(?:"
        r"(?P<positional>\d+\$)?"  # Optional positional specifier (e.g., 1$)
        r"[-+0 #]*"  # Optional flags
        r"(?:\d+|\*)?"  # Optional width
        r"(?:\.(?:\d+|\*))?"  # Optional precision
        r"(?:hh|h|ll|l|L|z|j|t)?"  # Optional length modifier
        r"[diouxXeEfFgGaAcspn@]"  # Conversion specifier
        r"|%"  # OR literal %% (escaped percent)
        r")"
    )

    def validate(self, source: str, translation: str) -> Tuple[bool, List[PlaceholderIssue]]:
        """
        Validate that placeholders in source match those in translation.

        Args:
            source: Original source text
            translation: Translated text

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        source_placeholders = self._extract_placeholders(source)
        trans_placeholders = self._extract_placeholders(translation)

        # Check count mismatch
        if len(source_placeholders) != len(trans_placeholders):
            issues.append(
                PlaceholderIssue(
                    error_type="count_mismatch",
                    message=f"Placeholder count mismatch: source has {len(source_placeholders)}, "
                    f"translation has {len(trans_placeholders)}",
                    severity="critical",
                )
            )

        # Check for missing placeholders
        source_set = set(source_placeholders)
        trans_set = set(trans_placeholders)

        missing = source_set - trans_set
        extra = trans_set - source_set

        for placeholder in missing:
            issues.append(
                PlaceholderIssue(
                    error_type="missing",
                    message=f"Missing placeholder in translation: {placeholder}",
                    severity="critical",
                )
            )

        for placeholder in extra:
            issues.append(
                PlaceholderIssue(
                    error_type="extra",
                    message=f"Extra placeholder in translation: {placeholder}",
                    severity="critical",
                )
            )

        # For non-positional placeholders, check if order changed (warning, not critical)
        if not issues:  # Only check order if no other issues
            source_non_positional = [p for p in source_placeholders if "$" not in p]
            trans_non_positional = [p for p in trans_placeholders if "$" not in p]

            if source_non_positional != trans_non_positional:
                # Check if it's just reordering
                if sorted(source_non_positional) == sorted(trans_non_positional):
                    issues.append(
                        PlaceholderIssue(
                            error_type="order_changed",
                            message="Non-positional placeholder order changed "
                            "(may cause runtime issues)",
                            severity="warning",
                        )
                    )

        is_valid = not any(issue.severity == "critical" for issue in issues)
        return is_valid, issues

    def _extract_placeholders(self, text: str) -> List[str]:
        """Extract all placeholders from text."""
        matches = self.PLACEHOLDER_PATTERN.findall(text)
        # The regex returns the full match, rebuild them
        placeholders = []
        for match in self.PLACEHOLDER_PATTERN.finditer(text):
            placeholders.append(match.group(0))
        return placeholders

    def get_placeholder_count(self, text: str) -> int:
        """Get the number of placeholders in text."""
        return len(self._extract_placeholders(text))

    def has_placeholders(self, text: str) -> bool:
        """Check if text contains any placeholders."""
        return bool(self.PLACEHOLDER_PATTERN.search(text))

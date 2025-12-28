"""Service for tracking LLM review history to avoid redundant checks."""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class ReviewRecord:
    """Record of a single translation review."""
    content_hash: str
    reviewed_at: str
    passed: bool
    issues: List[str] = field(default_factory=list)


class ReviewHistoryService:
    """
    Tracks LLM review history to skip unchanged translations.

    Stores a hash of source + translation for each reviewed string.
    If the hash matches on next review, the translation is skipped.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize the review history service.

        Args:
            base_dir: Directory to store review history files
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_history_path(self, file_id: str) -> Path:
        """Get the path to the history file for a given file ID."""
        return self.base_dir / f"{file_id}.review_history.json"

    def _load_history(self, file_id: str) -> Dict[str, Any]:
        """Load history from disk, with caching."""
        if file_id in self._cache:
            return self._cache[file_id]

        history_path = self._get_history_path(file_id)
        if history_path.exists():
            try:
                data = json.loads(history_path.read_text())
                self._cache[file_id] = data
                return data
            except (json.JSONDecodeError, IOError):
                pass

        # Initialize empty history
        data = {"file_id": file_id, "reviews": {}}
        self._cache[file_id] = data
        return data

    def _save_history(self, file_id: str) -> None:
        """Save history to disk."""
        if file_id not in self._cache:
            return

        history_path = self._get_history_path(file_id)
        history_path.write_text(json.dumps(self._cache[file_id], indent=2))

    def _compute_hash(self, source: str, translation: str) -> str:
        """Compute a hash of source + translation."""
        content = f"{source}||{translation}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get_review(self, file_id: str, language: str, key: str) -> Optional[ReviewRecord]:
        """
        Get the review record for a specific translation.

        Args:
            file_id: The file ID
            language: Target language code
            key: String key

        Returns:
            ReviewRecord if found, None otherwise
        """
        history = self._load_history(file_id)
        lang_reviews = history.get("reviews", {}).get(language, {})
        record_data = lang_reviews.get(key)

        if record_data:
            return ReviewRecord(
                content_hash=record_data["content_hash"],
                reviewed_at=record_data["reviewed_at"],
                passed=record_data["passed"],
                issues=record_data.get("issues", []),
            )
        return None

    def is_unchanged(
        self, file_id: str, language: str, key: str, source: str, translation: str
    ) -> bool:
        """
        Check if a translation is unchanged since last review.

        Args:
            file_id: The file ID
            language: Target language code
            key: String key
            source: Source text
            translation: Translated text

        Returns:
            True if the translation was previously reviewed and hasn't changed
        """
        record = self.get_review(file_id, language, key)
        if not record:
            return False

        current_hash = self._compute_hash(source, translation)
        return record.content_hash == current_hash

    def record_review(
        self,
        file_id: str,
        language: str,
        key: str,
        source: str,
        translation: str,
        passed: bool,
        issues: Optional[List[str]] = None,
    ) -> None:
        """
        Record a review result.

        Args:
            file_id: The file ID
            language: Target language code
            key: String key
            source: Source text
            translation: Translated text
            passed: Whether the review passed
            issues: List of issues found (if any)
        """
        history = self._load_history(file_id)

        if "reviews" not in history:
            history["reviews"] = {}
        if language not in history["reviews"]:
            history["reviews"][language] = {}

        record = ReviewRecord(
            content_hash=self._compute_hash(source, translation),
            reviewed_at=datetime.now().isoformat(),
            passed=passed,
            issues=issues or [],
        )

        history["reviews"][language][key] = asdict(record)
        self._save_history(file_id)

    def clear_key(self, file_id: str, language: str, key: str) -> None:
        """
        Clear the review history for a specific key.

        Call this when a translation is manually edited.

        Args:
            file_id: The file ID
            language: Target language code
            key: String key to clear
        """
        history = self._load_history(file_id)
        lang_reviews = history.get("reviews", {}).get(language, {})

        if key in lang_reviews:
            del lang_reviews[key]
            self._save_history(file_id)

    def clear_language(self, file_id: str, language: str) -> None:
        """
        Clear all review history for a language.

        Args:
            file_id: The file ID
            language: Target language code to clear
        """
        history = self._load_history(file_id)

        if language in history.get("reviews", {}):
            del history["reviews"][language]
            self._save_history(file_id)

    def clear_file(self, file_id: str) -> None:
        """
        Clear all review history for a file.

        Args:
            file_id: The file ID to clear
        """
        if file_id in self._cache:
            del self._cache[file_id]

        history_path = self._get_history_path(file_id)
        if history_path.exists():
            history_path.unlink()

    def get_stats(self, file_id: str, language: str) -> Dict[str, int]:
        """
        Get review statistics for a language.

        Args:
            file_id: The file ID
            language: Target language code

        Returns:
            Dict with total, passed, and failed counts
        """
        history = self._load_history(file_id)
        lang_reviews = history.get("reviews", {}).get(language, {})

        total = len(lang_reviews)
        passed = sum(1 for r in lang_reviews.values() if r.get("passed", False))

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        }

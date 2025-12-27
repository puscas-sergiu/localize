"""Direct file service for accessing local .xcstrings files."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from .file_storage import FileStorage
from ..services.translation_service import TranslationService


@dataclass
class DirectFileConfig:
    """Configuration for direct file access mode."""
    file_path: str          # Absolute path to .xcstrings file
    file_id: str            # Links to temp storage in FileStorage
    configured_at: str      # ISO timestamp
    last_synced: Optional[str] = None  # Last refresh/apply timestamp

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DirectFileConfig":
        return cls(**data)


class DirectFileService:
    """Manages direct file system access for configured paths."""

    def __init__(self, file_storage: FileStorage):
        self.file_storage = file_storage
        self.config_file = Path(tempfile.gettempdir()) / "localize-web" / "direct_config.json"
        self._config: Optional[DirectFileConfig] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from disk."""
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text())
                self._config = DirectFileConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError):
                self._config = None

    def _save_config(self) -> None:
        """Save configuration to disk."""
        self.config_file.parent.mkdir(exist_ok=True)
        if self._config:
            self.config_file.write_text(json.dumps(self._config.to_dict(), indent=2))
        elif self.config_file.exists():
            self.config_file.unlink()

    def configure(self, file_path: str) -> tuple[DirectFileConfig, dict]:
        """
        Configure a direct file path and load it into temp storage.

        Args:
            file_path: Absolute path to .xcstrings file

        Returns:
            Tuple of (DirectFileConfig, stats dict)

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file can't be read
            ValueError: If file is not a valid .xcstrings file
        """
        path = Path(file_path)

        # Validate path
        if not path.is_absolute():
            raise ValueError(f"Path must be absolute: {file_path}")

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path.suffix == ".xcstrings":
            raise ValueError(f"File must be a .xcstrings file: {file_path}")

        # Read and validate content
        try:
            content = path.read_bytes()
        except PermissionError:
            raise PermissionError(f"Permission denied: {file_path}")

        # Validate JSON structure
        try:
            data = json.loads(content)
            if "strings" not in data or "sourceLanguage" not in data:
                raise ValueError("Invalid .xcstrings structure: missing 'strings' or 'sourceLanguage'")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file: {e}")

        # Save to FileStorage
        metadata = self.file_storage.save(content, path.name)

        # Create configuration
        now = datetime.now().isoformat()
        self._config = DirectFileConfig(
            file_path=str(path),
            file_id=metadata.file_id,
            configured_at=now,
            last_synced=now,
        )
        self._save_config()

        # Get stats
        service = TranslationService()
        stats = service.get_file_stats(content.decode("utf-8"))

        return self._config, stats

    def get_config(self) -> Optional[DirectFileConfig]:
        """Get current direct file configuration."""
        return self._config

    def clear_config(self) -> bool:
        """
        Clear the configured path (switch back to upload mode).

        Returns:
            True if config was cleared, False if no config existed
        """
        if not self._config:
            return False

        # Optionally delete the temp file
        if self._config.file_id:
            self.file_storage.delete(self._config.file_id)

        self._config = None
        self._save_config()
        return True

    def refresh(self) -> tuple[bool, dict | str]:
        """
        Reload content from configured path into temp storage.

        Returns:
            Tuple of (success, stats dict or error message)
        """
        if not self._config:
            return False, "No direct file configured"

        path = Path(self._config.file_path)

        if not path.exists():
            return False, f"File not found: {self._config.file_path}"

        try:
            content = path.read_bytes()
        except PermissionError:
            return False, f"Permission denied: {self._config.file_path}"

        # Validate JSON
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in file: {e}"

        # Update temp storage
        self.file_storage.update_content(self._config.file_id, content)

        # Update last synced
        self._config.last_synced = datetime.now().isoformat()
        self._save_config()

        # Get stats
        service = TranslationService()
        stats = service.get_file_stats(content.decode("utf-8"))

        return True, stats

    def apply(self) -> tuple[bool, str]:
        """
        Write current temp storage content to configured path.

        Returns:
            Tuple of (success, message)
        """
        if not self._config:
            return False, "No direct file configured"

        path = Path(self._config.file_path)

        # Get content from temp storage
        content = self.file_storage.get_content(self._config.file_id)
        if content is None:
            return False, "File content not found in storage"

        # Validate JSON before writing
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in storage: {e}"

        # Write to file
        try:
            path.write_bytes(content)
        except PermissionError:
            return False, f"Permission denied: {self._config.file_path}"
        except Exception as e:
            return False, f"Failed to write file: {e}"

        # Update last synced
        self._config.last_synced = datetime.now().isoformat()
        self._save_config()

        return True, f"Successfully applied changes to {path.name}"

    def get_file_info(self) -> Optional[dict]:
        """
        Get info about the configured file (exists, last modified, etc.).

        Returns:
            Dict with file info, or None if not configured
        """
        if not self._config:
            return None

        path = Path(self._config.file_path)

        info = {
            "file_path": self._config.file_path,
            "file_name": path.name,
            "file_exists": path.exists(),
            "last_modified": None,
            "size_bytes": None,
        }

        if path.exists():
            stat = path.stat()
            info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            info["size_bytes"] = stat.st_size

        return info

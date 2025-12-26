"""File storage service for uploaded .xcstrings files."""

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class FileMetadata:
    """Metadata for an uploaded file."""
    file_id: str
    original_name: str
    upload_time: str
    size_bytes: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FileMetadata":
        return cls(**data)


class FileStorage:
    """Manages temporary storage of uploaded .xcstrings files."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(tempfile.gettempdir()) / "localize-web"
        self.base_dir.mkdir(exist_ok=True)

    def save(self, content: bytes, original_name: str) -> FileMetadata:
        """
        Save uploaded file content and return metadata.

        Args:
            content: File content as bytes
            original_name: Original filename

        Returns:
            FileMetadata with file_id and other info
        """
        file_id = str(uuid.uuid4())
        file_path = self._get_file_path(file_id)
        meta_path = self._get_meta_path(file_id)

        # Write file content
        file_path.write_bytes(content)

        # Create and save metadata
        metadata = FileMetadata(
            file_id=file_id,
            original_name=original_name,
            upload_time=datetime.now().isoformat(),
            size_bytes=len(content),
        )
        meta_path.write_text(json.dumps(metadata.to_dict()))

        return metadata

    def get_content(self, file_id: str) -> Optional[bytes]:
        """Get file content by ID."""
        file_path = self._get_file_path(file_id)
        if not file_path.exists():
            return None
        return file_path.read_bytes()

    def get_content_string(self, file_id: str) -> Optional[str]:
        """Get file content as string by ID."""
        content = self.get_content(file_id)
        if content is None:
            return None
        return content.decode("utf-8")

    def get_metadata(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata by ID."""
        meta_path = self._get_meta_path(file_id)
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text())
        return FileMetadata.from_dict(data)

    def update_content(self, file_id: str, content: bytes) -> bool:
        """Update file content."""
        file_path = self._get_file_path(file_id)
        if not file_path.exists():
            return False
        file_path.write_bytes(content)

        # Update size in metadata
        meta = self.get_metadata(file_id)
        if meta:
            meta.size_bytes = len(content)
            meta_path = self._get_meta_path(file_id)
            meta_path.write_text(json.dumps(meta.to_dict()))

        return True

    def delete(self, file_id: str) -> bool:
        """Delete a file by ID."""
        file_path = self._get_file_path(file_id)
        meta_path = self._get_meta_path(file_id)

        deleted = False
        if file_path.exists():
            file_path.unlink()
            deleted = True
        if meta_path.exists():
            meta_path.unlink()
            deleted = True

        return deleted

    def list_files(self) -> list[FileMetadata]:
        """List all stored files."""
        files = []
        for meta_file in self.base_dir.glob("*.meta"):
            try:
                data = json.loads(meta_file.read_text())
                files.append(FileMetadata.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by upload time, newest first
        files.sort(key=lambda f: f.upload_time, reverse=True)
        return files

    def exists(self, file_id: str) -> bool:
        """Check if a file exists."""
        return self._get_file_path(file_id).exists()

    def get_file_path(self, file_id: str) -> Optional[Path]:
        """Get the actual file path for direct access."""
        path = self._get_file_path(file_id)
        return path if path.exists() else None

    def _get_file_path(self, file_id: str) -> Path:
        """Get path for file content."""
        return self.base_dir / f"{file_id}.xcstrings"

    def _get_meta_path(self, file_id: str) -> Path:
        """Get path for metadata file."""
        return self.base_dir / f"{file_id}.meta"

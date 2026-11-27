"""Stores task files on the owner's own server under backend/private-storage/task-files/.

Not under backend/storage/: main.py serves that folder publicly (for logos), which would let
anyone with a path download task files without a permission check. Files here are only reachable
through the authenticated download endpoints.

Files are saved under generated names, never the uploaded name, so a crafted file name cannot
escape the storage folder. The original name is kept in the database for downloads.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from app.services.authentication_service import AuthenticationError

MAX_TASK_FILE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB: long videos can be large.
_CHUNK_BYTES = 1024 * 1024


def _size_label(size: int) -> str:
    """1048576 -> "1 MB", 2147483648 -> "2 GB"."""
    for unit, scale in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size >= scale:
            value = size / scale
            return f"{value:.0f} {unit}" if value == int(value) else f"{value:.1f} {unit}"
    return f"{size} bytes"


@dataclass(frozen=True)
class StoredFile:
    storage_path: str
    file_name: str
    mime_type: str
    size_bytes: int


def clean_file_name(name: str | None) -> str:
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    return base[:200] or "file"


class TaskFileStorage:
    def __init__(self, root: Path | None = None, max_bytes: int = MAX_TASK_FILE_BYTES):
        self.root = (root or Path("private-storage/task-files")).resolve()
        self.max_bytes = max_bytes

    def save(self, company_id: UUID, task_id: UUID, upload: UploadFile) -> StoredFile:
        relative = Path(str(company_id)) / str(task_id) / uuid4().hex
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        try:
            with target.open("wb") as handle:
                while chunk := upload.file.read(_CHUNK_BYTES):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise AuthenticationError(
                            413,
                            "FILE_TOO_LARGE",
                            f"Files can be at most {_size_label(self.max_bytes)}.",
                        )
                    handle.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        if size == 0:
            target.unlink(missing_ok=True)
            raise AuthenticationError(422, "EMPTY_FILE", "The uploaded file is empty.")
        return StoredFile(
            storage_path=relative.as_posix(),
            file_name=clean_file_name(upload.filename),
            mime_type=(upload.content_type or "application/octet-stream")[:200],
            size_bytes=size,
        )

    def save_bytes(
        self, company_id: UUID, owner_id: UUID, content: bytes, file_name: str, mime_type: str
    ) -> StoredFile:
        """A file made by the app itself (e.g. a PDF attached to a system mail)."""
        if not content:
            raise AuthenticationError(422, "EMPTY_FILE", "The file is empty.")
        if len(content) > self.max_bytes:
            raise AuthenticationError(
                413, "FILE_TOO_LARGE", f"Files can be at most {_size_label(self.max_bytes)}."
            )
        relative = Path(str(company_id)) / str(owner_id) / uuid4().hex
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StoredFile(
            storage_path=relative.as_posix(),
            file_name=clean_file_name(file_name),
            mime_type=mime_type[:200],
            size_bytes=len(content),
        )

    def path_for(self, storage_path: str) -> Path:
        path = (self.root / storage_path).resolve()
        if not path.is_relative_to(self.root):
            raise AuthenticationError(404, "FILE_NOT_FOUND", "File was not found.")
        if not path.is_file():
            raise AuthenticationError(
                404, "FILE_MISSING", "The file record exists but the stored file is missing."
            )
        return path

    def delete(self, storage_path: str) -> None:
        path = (self.root / storage_path).resolve()
        if path.is_relative_to(self.root):
            path.unlink(missing_ok=True)

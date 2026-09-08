"""Photo upload handling for student and staff portraits.

``POST /api/v1/media/upload`` stores the bytes on disk under
``settings.MEDIA_ROOT`` and returns the URL that callers put into
``Student.photo_url`` / ``Teacher.photo_url`` / ``User.photo_url``.  The
database only ever holds the (max 500 character) URL — never image bytes.

Hardening notes:

* the client-supplied ``Content-Type`` is **not** trusted: the payload's magic
  bytes decide the accepted type and the stored extension;
* files are renamed to ``<uuid4>.<ext>`` so an uploaded filename can never
  traverse directories or overwrite another tenant's portrait;
* reads go through :meth:`MediaService.resolve_safe`, which rejects any path
  that escapes the media root;
* the size cap is ``settings.MAX_UPLOAD_SIZE_MB``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, status

from app.core.config import settings

#: Accepted image types mapped to the extension used when storing them.
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_SIGNATURES: Tuple[Tuple[bytes, int, str], ...] = (
    (b"\xff\xd8\xff", 0, "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"GIF87a", 0, "image/gif"),
    (b"GIF89a", 0, "image/gif"),
    (b"RIFF", 0, "image/webp"),  # confirmed by the "WEBP" marker at offset 8
)


@dataclass(frozen=True)
class StoredMedia:
    """Result of a successful upload."""

    filename: str
    relative_path: str
    url: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class MediaService:
    @staticmethod
    def root() -> Path:
        """Absolute media root (relative settings resolve against the CWD)."""
        return Path(settings.MEDIA_ROOT).expanduser().resolve()

    @staticmethod
    def upload_root() -> Path:
        return MediaService.root() / "uploads"

    @staticmethod
    def ensure_directories() -> Path:
        upload_root = MediaService.upload_root()
        upload_root.mkdir(parents=True, exist_ok=True)
        return upload_root

    @staticmethod
    def max_bytes() -> int:
        return max(1, int(settings.MAX_UPLOAD_SIZE_MB)) * 1024 * 1024

    @staticmethod
    def detect_content_type(data: bytes) -> Optional[str]:
        """Sniff the real image type from magic bytes (``None`` if unknown)."""
        for signature, offset, content_type in _SIGNATURES:
            if data[offset:offset + len(signature)] != signature:
                continue
            if content_type == "image/webp" and data[8:12] != b"WEBP":
                continue
            return content_type
        return None

    @staticmethod
    def public_url(relative_path: str) -> str:
        prefix = (settings.MEDIA_URL_PREFIX or "/media").rstrip("/")
        return f"{prefix}/{relative_path.lstrip('/')}"

    @staticmethod
    def save_upload(
        data: bytes,
        declared_content_type: Optional[str] = None,
        subdir: str = "uploads",
    ) -> StoredMedia:
        """Validate and persist an upload, returning its public metadata."""
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
            )
        limit = MediaService.max_bytes()
        if len(data) > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Photo exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit "
                    f"({len(data)} bytes received)"
                ),
            )

        content_type = MediaService.detect_content_type(data)
        if content_type is None:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "Unsupported image type. Upload a JPEG, PNG, WEBP or GIF portrait "
                    f"(declared type was '{declared_content_type or 'unknown'}')."
                ),
            )

        extension = ALLOWED_IMAGE_TYPES[content_type]
        filename = f"{uuid.uuid4().hex}{extension}"
        relative_path = f"{subdir.strip('/')}/{filename}"

        target = MediaService.root() / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        return StoredMedia(
            filename=filename,
            relative_path=relative_path,
            url=MediaService.public_url(relative_path),
            content_type=content_type,
            size_bytes=len(data),
            uploaded_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def resolve_safe(relative_path: str) -> Path:
        """Resolve a served path inside the media root (404 on escape/absence)."""
        not_found = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found"
        )
        candidate = (relative_path or "").strip().lstrip("/")
        if not candidate or "\x00" in candidate:
            raise not_found

        root = MediaService.root()
        try:
            target = (root / candidate).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            raise not_found from None
        if not target.is_file():
            raise not_found
        return target

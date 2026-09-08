"""Photo/media schemas shared by the student, teacher and media endpoints.

``photo_url`` is stored as a plain string on ``students.photo_url``,
``teachers.photo_url`` and ``users.photo_url``.  Two shapes are accepted:

* an absolute ``http(s)`` URL (CDN / object storage), or
* a root-relative local path (``/media/uploads/<file>.jpg``) as returned by
  ``POST /api/v1/media/upload``.

Everything else — ``data:`` URIs (they blow past the 500-character column and
embed binary in the database), protocol-relative ``//host/x`` URLs, Windows
paths and strings with embedded whitespace — is rejected at the schema layer so
no router has to re-implement the check.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

#: Column bound for ``*_photo_url`` (``String(500)`` in the models).
PHOTO_URL_MAX_LENGTH = 500

_ALLOWED_SCHEMES = ("http://", "https://")


def normalize_photo_url(value: object) -> Optional[str]:
    """Validate and canonicalise a ``photo_url`` value (``None`` clears it)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("photo_url must be a string")

    candidate = value.strip()
    if not candidate:
        # An empty string is treated as "no photo" so clients can clear a
        # portrait without sending an explicit null.
        return None
    if len(candidate) > PHOTO_URL_MAX_LENGTH:
        raise ValueError(f"photo_url must be at most {PHOTO_URL_MAX_LENGTH} characters")
    if any(character.isspace() or ord(character) < 32 for character in candidate):
        raise ValueError("photo_url must not contain whitespace or control characters")

    lowered = candidate.lower()
    if lowered.startswith(_ALLOWED_SCHEMES):
        return candidate
    if candidate.startswith("//"):
        raise ValueError("protocol-relative photo_url values are not allowed")
    if candidate.startswith("/"):
        segments = candidate.split("/")[1:]  # drop the leading empty string
        if ".." in segments:
            raise ValueError("photo_url must not contain '..' path segments")
        if any(not segment for segment in segments[:-1]):
            raise ValueError("photo_url must not contain empty path segments")
        return candidate
    raise ValueError(
        "photo_url must be an absolute http(s) URL or a root-relative path such as /media/uploads/photo.jpg"
    )


#: Reusable ``photo_url`` field type (optional, validated, length-bounded).
#: The length bound lives in :func:`normalize_photo_url` rather than in
#: ``Field(max_length=...)`` because that constraint would also be applied to
#: the ``None`` branch of the optional and raise a ``TypeError``.
PhotoUrl = Annotated[Optional[str], BeforeValidator(normalize_photo_url)]


class PhotoUrlUpdate(BaseModel):
    """Body for "set/clear this record's portrait" endpoints."""

    model_config = ConfigDict(extra="forbid")

    photo_url: PhotoUrl = None


class MediaUploadResponse(BaseModel):
    """Result of ``POST /api/v1/media/upload``.

    ``url`` and ``photo_url`` carry the same value; ``photo_url`` exists so the
    payload can be forwarded straight into a student/teacher update body.
    """

    model_config = ConfigDict(from_attributes=True)

    url: str
    photo_url: str
    filename: str
    content_type: str
    size_bytes: int = Field(..., ge=0)
    uploaded_at: datetime

"""Photo upload helper — ``/api/v1/media/upload`` — plus public file serving.

Flow used by the web client:

1. ``POST /api/v1/media/upload`` with a ``multipart/form-data`` ``file`` field
   (JPEG/PNG/WEBP/GIF, capped at ``settings.MAX_UPLOAD_SIZE_MB``);
2. take ``photo_url`` from the response;
3. ``PATCH`` it onto the record (``/api/v1/students``-style student update,
   ``/api/v1/teachers/{id}`` or ``/api/v1/school/teachers/{id}``).

The database stores only the URL. Files are served back from
``settings.MEDIA_URL_PREFIX`` (``/media`` by default) with unguessable UUID
filenames; the serving route resolves every path through
:meth:`MediaService.resolve_safe` so it cannot be used to read outside the
media root. Uploads require a school-tenant login, reads are unauthenticated
(portraits are rendered by plain ``<img>`` tags).
"""
from __future__ import annotations

import mimetypes
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import require_school_tenant
from app.core.config import settings
from app.models.tenancy import User
from app.schemas.media import MediaUploadResponse
from app.services.media_service import ALLOWED_IMAGE_TYPES, MediaService

router = APIRouter(prefix="/v1/media", tags=["media"])

#: Mounted at the application root so portraits resolve to ``/media/...``.
files_router = APIRouter(tags=["media"])

_CHUNK_SIZE = 1024 * 1024


async def _read_limited(upload: UploadFile) -> bytes:
    """Stream an upload into memory, aborting as soon as it is too large."""
    limit = MediaService.max_bytes()
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Photo exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit; "
                    "upload a smaller portrait"
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a portrait and get back its photo_url",
)
async def upload_media(
    file: UploadFile = File(..., description="JPEG, PNG, WEBP or GIF image"),
    user: User = Depends(require_school_tenant),
):
    data = await _read_limited(file)
    stored = MediaService.save_upload(data, declared_content_type=file.content_type)
    return MediaUploadResponse(
        url=stored.url,
        photo_url=stored.url,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        uploaded_at=stored.uploaded_at,
    )


@router.get(
    "/accepted-types",
    summary="Image types and size limit accepted by /upload",
)
async def accepted_types(user: User = Depends(require_school_tenant)):
    return {
        "accepted_content_types": sorted(ALLOWED_IMAGE_TYPES),
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "url_prefix": settings.MEDIA_URL_PREFIX,
    }


@files_router.get(
    f"{settings.MEDIA_URL_PREFIX.rstrip('/')}/{{relative_path:path}}",
    summary="Serve an uploaded media file",
)
async def serve_media(relative_path: str):
    target = MediaService.resolve_safe(relative_path)
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(
        target,
        media_type=media_type,
        # Portraits are cacheable but must be revalidated after a re-upload.
        headers={"Cache-Control": "private, max-age=3600"},
    )

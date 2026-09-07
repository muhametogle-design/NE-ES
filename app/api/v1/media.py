"""Local photo uploads for the student/teacher photo_url fields.

Upload writes require a school user; /static URLs are intentionally public.
Only the declared MIME type and byte size are validated, not image contents.
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import require_school_tenant
from app.schemas.media import PhotoUploadResponse

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("uploads")
MAX_PHOTO_SIZE = 5 * 1024 * 1024
PHOTO_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

router = APIRouter(prefix="/v1/media", tags=["media"])


def _save_photo(content: bytes, extension: str) -> str:
    """Run blocking disk I/O off the event loop; never overwrite an existing file."""
    photo_dir = UPLOADS_DIR / "photos"
    photo_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        filename = f"{uuid.uuid4().hex}{extension}"
        destination = photo_dir / filename
        try:
            output = destination.open("xb")
        except FileExistsError:
            # UUID collisions are extremely unlikely; exclusive creation also
            # makes concurrent uploads safe without a check-then-write race.
            continue
        try:
            with output:
                output.write(content)
        except OSError:
            # Close before removing so cleanup also works on Windows.
            destination.unlink(missing_ok=True)
            raise
        return filename
    raise OSError("Could not allocate a unique photo filename")


@router.post(
    "/upload",
    response_model=PhotoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_school_tenant)],
)
async def upload_photo(file: UploadFile = File(...)) -> PhotoUploadResponse:
    try:
        extension = PHOTO_EXTENSIONS.get((file.content_type or "").lower())
        if extension is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG, and WebP photos are allowed")

        # Read at most one byte beyond the cap, not an unbounded request into
        # memory. Count actual payload bytes, not client-supplied length headers.
        content = await file.read(MAX_PHOTO_SIZE + 1)
        if not content:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Photo file must not be empty")
        if len(content) > MAX_PHOTO_SIZE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Photo file must not exceed 5 MB")

        try:
            filename = await run_in_threadpool(_save_photo, content, extension)
        except OSError:
            logger.exception("Unable to save uploaded photo")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Unable to save photo") from None
        return PhotoUploadResponse(photo_url=f"/static/photos/{filename}")
    finally:
        await file.close()

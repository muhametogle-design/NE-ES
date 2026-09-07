"""The public relative URL can be passed directly to photo_url in profile CRUD."""
from pydantic import BaseModel


class PhotoUploadResponse(BaseModel):
    photo_url: str

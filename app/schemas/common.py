from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional, Any

T = TypeVar("T")

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None

class StatusResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    pages: int

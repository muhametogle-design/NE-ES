from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    staff_identifier: Optional[str] = None
    pin: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    school_id: Optional[int] = None
    email: str
    role: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    staff_identifier: Optional[str] = None
    is_department_head: bool = False
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class SetPinRequest(BaseModel):
    pin: str

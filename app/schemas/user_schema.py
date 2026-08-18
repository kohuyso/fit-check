from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime

# Dữ liệu Mobile gửi lên khi Đăng ký
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    preferred_style: List[str] = ["Casual"]

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Email không được để trống.")
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Mật khẩu không được để trống.")
        if len(v.strip()) < 6:
            raise ValueError("Mật khẩu phải chứa ít nhất 6 ký tự.")
        return v.strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

# Dữ liệu Mobile gửi lên khi Đăng nhập bằng Google
class GoogleLoginRequest(BaseModel):
    id_token: str

# Dữ liệu Backend trả về cho Mobile (Ẩn mật khẩu đi)
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    google_id: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_style: List[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Cấu trúc Token trả về khi Đăng nhập thành công
class Token(BaseModel):
    access_token: str
    token_type: str

class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_style: Optional[List[str]] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
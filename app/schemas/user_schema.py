from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Dữ liệu Mobile gửi lên khi Đăng ký
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    preferred_style: List[str] = ["Casual"]

# Dữ liệu Backend trả về cho Mobile (Ẩn mật khẩu đi)
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    preferred_style: List[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Cấu trúc Token trả về khi Đăng nhập thành công
class Token(BaseModel):
    access_token: str
    token_type: str
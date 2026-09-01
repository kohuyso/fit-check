import os
import uuid
from typing import Optional, cast, Dict, Any
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.logger import logger
from app.models.user import User
from app.schemas import user_schema
from app.services.storage import upload_image_to_s3

def register_user(db: Session, user_in: user_schema.UserCreate) -> User:
    """Xử lý nghiệp vụ đăng ký tài khoản người dùng mới"""
    email = user_in.email.strip().lower() if user_in.email else ""
    password = user_in.password.strip() if user_in.password else ""
    full_name = user_in.full_name.strip() if user_in.full_name else None

    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Email không được để trống."
        )

    if not password or len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Mật khẩu không được để trống và phải chứa ít nhất 6 ký tự."
        )

    user_exists = db.query(User).filter(User.email == email).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký trên hệ thống FitCheck AI."
        )
    
    hashed_password = security.get_password_hash(password)
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        preferred_style=user_in.preferred_style or ["Casual"]
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"New user registered successfully: {new_user.email}")
    return new_user

def authenticate_user(db: Session, username: str, password: str) -> User:
    """Xác thực người dùng qua email và mật khẩu"""
    email = username.strip().lower() if username else ""
    raw_password = password.strip() if password else ""

    if not email or not raw_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập đầy đủ Email và Mật khẩu."
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(raw_password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị tạm khóa hoặc ngừng hoạt động."
        )
    
    return user

def update_user_profile(
    db: Session, 
    current_user: User, 
    profile_in: user_schema.UserProfileUpdate
) -> User:
    """Cập nhật thông tin cá nhân và gu thời trang của người dùng"""
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name.strip()
    if profile_in.avatar_url is not None:
        current_user.avatar_url = profile_in.avatar_url.strip()
    if profile_in.preferred_style is not None:
        current_user.preferred_style = profile_in.preferred_style
    
    db.commit()
    db.refresh(current_user)
    return current_user

def upload_user_avatar(
    db: Session, 
    current_user: User, 
    file_bytes: bytes, 
    ext: str
) -> User:
    """Upload ảnh đại diện lên S3/local và cập nhật đường dẫn vào database"""
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )

    unique_filename = f"avatar_{uuid.uuid4()}.{ext}"
    object_name = f"avatars/{current_user.id}/{unique_filename}"
    s3_url = upload_image_to_s3(file_bytes, object_name)

    image_target = s3_url
    if not image_target:
        shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp_uploads")
        os.makedirs(shared_dir, exist_ok=True)
        mock_saved_path = os.path.join(shared_dir, unique_filename)
        with open(mock_saved_path, "wb") as buffer:
            buffer.write(file_bytes)
        image_target = mock_saved_path

    current_user.avatar_url = image_target
    db.commit()
    db.refresh(current_user)
    return current_user

def change_user_password(
    db: Session, 
    current_user: User, 
    current_password: str, 
    new_password: str
) -> None:
    """Đổi mật khẩu người dùng sau khi xác thực mật khẩu cũ"""
    current_pwd = current_password.strip() if current_password else ""
    new_pwd = new_password.strip() if new_password else ""

    if not current_pwd or not new_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập đầy đủ mật khẩu hiện tại và mật khẩu mới."
        )

    if not security.verify_password(current_pwd, cast(str, current_user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác."
        )

    if len(new_pwd) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải chứa ít nhất 6 ký tự."
        )

    current_user.hashed_password = security.get_password_hash(new_pwd)
    db.commit()

async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """Xác minh Google ID Token thông qua Google OAuth2 TokenInfo API"""
    google_token_info_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(google_token_info_url, timeout=10.0)
        except Exception as exc:
            logger.error(f"Lỗi kết nối khi xác minh Google Token: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể kết nối đến máy chủ xác thực của Google."
            )

    if response.status_code != status.HTTP_200_OK:
        logger.warning(f"Xác minh Google Token thất bại: {response.text}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID Token không hợp lệ hoặc đã hết hạn."
        )

    return response.json()

async def authenticate_google_user(db: Session, id_token: str) -> User:
    """Xác thực hoặc tạo mới User từ Google OAuth2 Token"""
    token_str = id_token.strip() if id_token else ""
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp Google ID token."
        )

    token_info = await verify_google_id_token(token_str)

    google_id = token_info.get("sub")
    email = token_info.get("email", "").strip().lower() if token_info.get("email") else ""
    full_name = token_info.get("name")
    avatar_url = token_info.get("picture")

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể trích xuất thông tin người dùng từ Google Token."
        )

    user = db.query(User).filter(User.google_id == google_id).first()

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.google_id = google_id
            if not user.full_name and full_name:
                user.full_name = full_name.strip()
            if not user.avatar_url and avatar_url:
                user.avatar_url = avatar_url.strip()
            db.commit()
            db.refresh(user)
        else:
            user = User(
                email=email,
                google_id=google_id,
                full_name=full_name.strip() if full_name else None,
                avatar_url=avatar_url.strip() if avatar_url else None,
                hashed_password=None,
                preferred_style=["Casual"]
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị tạm khóa hoặc ngừng hoạt động."
        )

    return user

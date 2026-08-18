import os
import uuid
import httpx
from typing import cast, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.config import settings
from app.database import get_db, redis_client
from app.models.user import User
from app.core import security
from app.core.logger import logger
from app.schemas import user_schema
from app.services.storage import upload_image_to_s3

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

security_bearer = HTTPBearer(auto_error=False)

def get_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy token xác thực.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

def get_current_user(token: str = Depends(get_token), db: Session = Depends(get_db)) -> User:
    """Hàm gác cổng: Giải mã token, check Blacklist Redis và trả về thông tin User hiện tại"""
    if redis_client.exists(f"blacklist:{token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã hết hạn hoặc đã đăng xuất.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin đăng nhập.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise credentials_exception
        
    return user

@router.post("/register", response_model=user_schema.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: user_schema.UserCreate, db: Session = Depends(get_db)):
    """API Đăng ký tài khoản mới từ màn hình Onboarding"""
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

@router.post("/login", response_model=user_schema.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """API Đăng nhập chuẩn OAuth2, trả về Bearer Token cho Mobile"""
    email = form_data.username.strip().lower() if form_data.username else ""
    password = form_data.password.strip() if form_data.password else ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập đầy đủ Email và Mật khẩu."
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, cast(str, user.hashed_password)):
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
    
    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(token: str = Depends(get_token)):
    """API Đăng xuất: Đưa JWT Token hiện tại vào Blacklist của Redis để hủy hiệu lực"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload.get("exp")
        
        ttl = 604800
        if exp:
            now = int(datetime.utcnow().timestamp())
            ttl = max(1, int(exp) - now)
            
        redis_client.setex(f"blacklist:{token}", ttl, "true")
    except JWTError:
        redis_client.setex(f"blacklist:{token}", 3600, "true")
        
    return {"status": "success", "message": "Đăng xuất thành công, phiên làm việc đã bị hủy."}

@router.get("/profile", response_model=user_schema.UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """API Lấy thông tin cá nhân của người dùng hiện tại"""
    return current_user

@router.put("/profile", response_model=user_schema.UserResponse)
def update_profile(
    profile_in: user_schema.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Cập nhật thông tin cá nhân và gu thời trang (preferred_style)"""
    if profile_in.full_name is not None:
        current_user.full_name = profile_in.full_name.strip()
    if profile_in.avatar_url is not None:
        current_user.avatar_url = profile_in.avatar_url.strip()
    if profile_in.preferred_style is not None:
        current_user.preferred_style = profile_in.preferred_style
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/profile/avatar", response_model=user_schema.UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Upload & Cập nhật ảnh đại diện (Avatar) cho Profile người dùng"""
    if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file ảnh định dạng PNG, JPG, JPEG hoặc WEBP."
        )

    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )

    ext = file.filename.split('.')[-1] if file.filename else 'png'
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

@router.post("/change-password")
def change_password(
    req: user_schema.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Thay đổi mật khẩu tài khoản người dùng"""
    current_pwd = req.current_password.strip() if req.current_password else ""
    new_pwd = req.new_password.strip() if req.new_password else ""

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
    return {"status": "success", "message": "Đổi mật khẩu thành công!"}

async def verify_google_id_token(id_token: str) -> dict:
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

    token_info = response.json()
    return token_info

@router.post("/google", response_model=user_schema.Token)
async def google_login(req: user_schema.GoogleLoginRequest, db: Session = Depends(get_db)):
    """API Đăng nhập hoặc Đăng ký bằng Google (Social Login)"""
    id_token = req.id_token.strip() if req.id_token else ""
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng cung cấp Google ID token."
        )

    token_info = await verify_google_id_token(id_token)

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

    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.core.config import settings
from app.database import get_db, redis_client
from app.models.user import User
from app.core import security
from app.schemas import user_schema
from app.services import user_service
from app.services.storage import validate_and_get_image_extension

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

security_bearer = HTTPBearer(auto_error=False)

def get_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> str:
    """Trích xuất token xác thực từ Authorization Header"""
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
    return user_service.register_user(db=db, user_in=user_in)

@router.post("/login", response_model=user_schema.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """API Đăng nhập chuẩn OAuth2, trả về Bearer Token cho Mobile"""
    user = user_service.authenticate_user(
        db=db, 
        username=form_data.username, 
        password=form_data.password
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
    return user_service.update_user_profile(
        db=db, 
        current_user=current_user, 
        profile_in=profile_in
    )

@router.post("/profile/avatar", response_model=user_schema.UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Upload & Cập nhật ảnh đại diện (Avatar) cho Profile người dùng"""
    ext = validate_and_get_image_extension(file)
    file_bytes = await file.read()
    return user_service.upload_user_avatar(
        db=db, 
        current_user=current_user, 
        file_bytes=file_bytes, 
        ext=ext
    )

@router.post("/change-password")
def change_password(
    req: user_schema.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Thay đổi mật khẩu tài khoản người dùng"""
    user_service.change_user_password(
        db=db, 
        current_user=current_user, 
        current_password=req.current_password or "", 
        new_password=req.new_password or ""
    )
    return {"status": "success", "message": "Đổi mật khẩu thành công!"}

@router.post("/google", response_model=user_schema.Token)
async def google_login(req: user_schema.GoogleLoginRequest, db: Session = Depends(get_db)):
    """API Đăng nhập hoặc Đăng ký bằng Google (Social Login)"""
    user = await user_service.authenticate_google_user(db=db, id_token=req.id_token or "")
    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
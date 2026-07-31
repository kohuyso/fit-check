from typing import cast
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.database import get_db, redis_client
from app.models.user import User
from app.core import security
from app.schemas import user_schema

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

security_bearer = HTTPBearer(auto_error=False)

def get_token(credentials: HTTPAuthorizationCredentials | None = Depends(security_bearer)) -> str:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy token xác thực.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

@router.post("/register", response_model=user_schema.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: user_schema.UserCreate, db: Session = Depends(get_db)):
    """API Đăng ký tài khoản mới từ màn hình Onboarding"""
    email = user_in.email.strip().lower() if user_in.email else ""
    password = user_in.password.strip() if user_in.password else ""
    full_name = user_in.full_name.strip() if user_in.full_name else None

    # 1. Kiểm tra đầu vào hợp lệ
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

    # 2. Kiểm tra email đã tồn tại chưa
    user_exists = db.query(User).filter(User.email == email).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký trên hệ thống FitCheck AI."
        )
    
    # 3. Tạo user mới và băm mật khẩu
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
    return new_user

@router.post("/login", response_model=user_schema.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """API Đăng nhập chuẩn OAuth2, trả về Bearer Token cho Mobile"""
    email = form_data.username.strip().lower() if form_data.username else ""
    password = form_data.password.strip() if form_data.password else ""

    # 1. Kiểm tra đầu vào hợp lệ
    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập đầy đủ Email và Mật khẩu."
        )

    # 2. Tìm user theo email và xác thực mật khẩu
    user = db.query(User).filter(User.email == email).first()
    if not user or not security.verify_password(password, cast(str, user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Kiểm tra tài khoản có bị khóa không
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đã bị tạm khóa hoặc ngừng hoạt động."
        )
    
    # 4. Tạo mã token kèm theo ID của user
    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(token: str = Depends(get_token), db: Session = Depends(get_db)):
    """Hàm gác cổng: Giải mã token, check Blacklist Redis và trả về thông tin User hiện tại"""
    # 1. Kiểm tra nhanh xem Token có nằm trong Blacklist của Redis không (do user đã bấm Đăng xuất)
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
        # Giải mã chuỗi token
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Tìm kiếm User trong Postgres
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        raise credentials_exception
        
    return user

@router.post("/logout")
def logout(token: str = Depends(get_token)):
    """API Đăng xuất: Đưa JWT Token hiện tại vào Blacklist của Redis để hủy hiệu lực"""
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        exp = payload.get("exp")
        
        ttl = 604800 # Mặc định 7 ngày nếu không đọc được exp
        if exp:
            now = int(datetime.utcnow().timestamp())
            ttl = max(1, int(exp) - now)
            
        redis_client.setex(f"blacklist:{token}", ttl, "true")
    except JWTError:
        redis_client.setex(f"blacklist:{token}", 3600, "true")
        
    return {"status": "success", "message": "Đăng xuất thành công, phiên làm việc đã bị hủy."}
from typing import Optional, List, Any, Dict, Union
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user_schema import UserCreate, UserProfileUpdate
from app.repositories.base import CRUDBase

class UserRepository(CRUDBase[User, UserCreate, UserProfileUpdate]):
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Tìm User theo email (chuẩn hoá lower case)"""
        return db.query(User).filter(User.email == email.strip().lower()).first()

    def get_by_google_id(self, db: Session, google_id: str) -> Optional[User]:
        """Tìm User theo Google ID"""
        return db.query(User).filter(User.google_id == google_id).first()

    def create_with_password(
        self, db: Session, *, obj_in: UserCreate, hashed_password: str
    ) -> User:
        """Tạo user mới với mật khẩu đã mã hoá"""
        db_obj = User(
            email=obj_in.email.strip().lower(),
            hashed_password=hashed_password,
            full_name=obj_in.full_name,
            preferred_style=obj_in.preferred_style or ["Casual"],
            is_active=True
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def create_google_user(
        self,
        db: Session,
        *,
        email: str,
        google_id: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> User:
        """Tạo user mới từ tài khoản Google"""
        db_obj = User(
            email=email.strip().lower(),
            google_id=google_id,
            hashed_password=None,
            full_name=full_name,
            avatar_url=avatar_url,
            preferred_style=["Casual"],
            is_active=True
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_avatar(self, db: Session, *, user: User, avatar_url: str) -> User:
        """Cập nhật avatar_url cho user"""
        user.avatar_url = avatar_url
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

user_repo = UserRepository(User)

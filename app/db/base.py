from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Lớp cơ sở DeclarativeBase cho tất cả SQLAlchemy ORM Models"""
    pass

# Đăng ký sẵn metadata của các model để hỗ trợ Alembic / startup lifespan
from app.models.user import User  # noqa: F401, E402
from app.models.closet import (  # noqa: F401, E402
    ClothingItem,
    OutfitCombo,
    UserCalendar,
    ChatMessage
)

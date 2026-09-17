from typing import List, Optional, Any, Dict
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.models.closet import ClothingItem, OutfitCombo, UserCalendar, ChatMessage
from app.schemas.closet_schema import ClothingItemCreate
from app.repositories.base import CRUDBase

class ClothingItemRepository(CRUDBase[ClothingItem, ClothingItemCreate, Any]):
    def get_by_id_and_user(self, db: Session, *, item_id: int, user_id: int) -> Optional[ClothingItem]:
        """Lấy một món đồ thuộc về user_id"""
        return db.query(ClothingItem).filter(
            ClothingItem.id == item_id,
            ClothingItem.user_id == user_id
        ).first()

    def get_by_user(
        self, db: Session, *, user_id: int, category: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[ClothingItem]:
        """Lấy danh sách món đồ của user, có thể lọc theo category"""
        query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
        if category:
            query = query.filter(ClothingItem.category.ilike(f"%{category.strip()}%"))
        return query.order_by(ClothingItem.created_at.desc()).offset(skip).limit(limit).all()

    def count_by_user(self, db: Session, *, user_id: int) -> int:
        """Đếm tổng số món đồ của user"""
        return db.query(func.count(ClothingItem.id)).filter(ClothingItem.user_id == user_id).scalar() or 0

    def get_favorites(self, db: Session, *, user_id: int) -> List[ClothingItem]:
        """Lấy danh sách món đồ yêu thích"""
        return db.query(ClothingItem).filter(
            ClothingItem.user_id == user_id,
            ClothingItem.is_favorite == True
        ).all()

    def toggle_favorite(self, db: Session, *, item: ClothingItem) -> ClothingItem:
        """Bật/tắt trạng thái yêu thích"""
        item.is_favorite = not item.is_favorite
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

class OutfitComboRepository(CRUDBase[OutfitCombo, Any, Any]):
    def get_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 50) -> List[OutfitCombo]:
        """Lấy danh sách các outfit combo của user kèm items liên kết"""
        return (
            db.query(OutfitCombo)
            .options(selectinload(OutfitCombo.items))
            .filter(OutfitCombo.user_id == user_id)
            .order_by(OutfitCombo.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_user(self, db: Session, *, outfit_id: int, user_id: int) -> Optional[OutfitCombo]:
        """Lấy chi tiết một bộ outfit thuộc về user"""
        return (
            db.query(OutfitCombo)
            .options(selectinload(OutfitCombo.items))
            .filter(OutfitCombo.id == outfit_id, OutfitCombo.user_id == user_id)
            .first()
        )

    def get_bookmarked(self, db: Session, *, user_id: int) -> List[OutfitCombo]:
        """Lấy danh sách outfit đã đánh dấu bookmark"""
        return (
            db.query(OutfitCombo)
            .options(selectinload(OutfitCombo.items))
            .filter(OutfitCombo.user_id == user_id, OutfitCombo.is_bookmarked == True)
            .all()
        )

class UserCalendarRepository(CRUDBase[UserCalendar, Any, Any]):
    def get_by_user_and_date(self, db: Session, *, user_id: int, date: datetime) -> Optional[UserCalendar]:
        """Lấy lịch phối đồ theo ngày"""
        return (
            db.query(UserCalendar)
            .options(selectinload(UserCalendar.outfit).selectinload(OutfitCombo.items))
            .filter(UserCalendar.user_id == user_id, func.date(UserCalendar.date) == date.date())
            .first()
        )

    def get_by_user_month(self, db: Session, *, user_id: int, year: int, month: int) -> List[UserCalendar]:
        """Lấy danh sách lịch trong tháng"""
        return (
            db.query(UserCalendar)
            .options(selectinload(UserCalendar.outfit).selectinload(OutfitCombo.items))
            .filter(
                UserCalendar.user_id == user_id,
                func.extract("year", UserCalendar.date) == year,
                func.extract("month", UserCalendar.date) == month
            )
            .order_by(UserCalendar.date.asc())
            .all()
        )

class ChatMessageRepository(CRUDBase[ChatMessage, Any, Any]):
    def get_history(self, db: Session, *, user_id: int, limit: int = 20) -> List[ChatMessage]:
        """Lấy lịch sử hội thoại gần nhất"""
        return (
            db.query(ChatMessage)
            .options(selectinload(ChatMessage.suggested_outfit).selectinload(OutfitCombo.items))
            .filter(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )

clothing_item_repo = ClothingItemRepository(ClothingItem)
outfit_combo_repo = OutfitComboRepository(OutfitCombo)
calendar_repo = UserCalendarRepository(UserCalendar)
chat_message_repo = ChatMessageRepository(ChatMessage)

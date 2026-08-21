from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.database import Base

EMBEDDING_DIM = 768

# Bảng trung gian (Many-to-Many): Một Outfit có nhiều món đồ, một món đồ nằm trong nhiều Outfit
outfit_item_association = Table(
    "outfit_item_association",
    Base.metadata,
    Column("outfit_id", Integer, ForeignKey("outfit_combos.id", ondelete="CASCADE")),
    Column("clothing_item_id", Integer, ForeignKey("clothing_items.id", ondelete="CASCADE"))
)

class ClothingItem(Base):
    __tablename__ = "clothing_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    image_url: Mapped[str] = mapped_column(String)   # Link ảnh PNG sạch nền lưu trên S3
    category: Mapped[str] = mapped_column(String, index=True)    # Shirts, Pants, Shoes, Jackets
    color_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # Ví dụ: White, Navy Blue
    color_code: Mapped[str] = mapped_column(String)  # Ví dụ: #1E293B
    style_tag: Mapped[str] = mapped_column(String, index=True)   # Formal, Casual
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_fixed: Mapped[bool] = mapped_column(Boolean, default=True)   # Đã qua xử lý AI tách nền hay chưa
    
    # Các trường mở rộng phục vụ RAG và Semantic Search
    description_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def name(self) -> str:
        color = self.color_name or ""
        return f"{color} {self.category}".strip()

    @property
    def style(self) -> str:
        return self.style_tag

    def build_searchable_text(self) -> str:
        """Tạo chuỗi mô tả phong phú chứa toàn bộ thông tin ngữ nghĩa phục vụ sinh embedding"""
        parts = [
            f"Category: {self.category}",
            f"Color: {self.color_name or self.color_code}",
            f"Style: {self.style_tag}"
        ]
        if self.description_text:
            parts.append(f"Description: {self.description_text}")
        return " | ".join(parts)

class OutfitCombo(Base):
    __tablename__ = "outfit_combos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    style_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # "Office Meeting", "Rainy Day"...
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Liên kết với danh sách các món đồ nằm trong bộ này
    items: Mapped[List[ClothingItem]] = relationship("ClothingItem", secondary=outfit_item_association)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class UserCalendar(Base):
    __tablename__ = "user_calendar"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    outfit_combo_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outfit_combos.id", ondelete="SET NULL"), nullable=True)
    
    date: Mapped[datetime] = mapped_column(DateTime)     # Ngày xếp lịch (Screen 6)
    event_title: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Ví dụ: "Office Meeting" (Screen 2)
    weather_status: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Ví dụ: "Rain, 22°C"
    notes: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Ghi chú thêm cho ngày (ví dụ: "Trang phục lịch sự")
    
    outfit: Mapped[Optional[OutfitCombo]] = relationship("OutfitCombo")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String) # "user" hoặc "assistant"
    content: Mapped[str] = mapped_column(String)
    suggested_outfit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outfit_combos.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[Optional[str]] = mapped_column(String, nullable=True) # "like" or "dislike"
    feedback_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    suggested_outfit: Mapped[Optional[OutfitCombo]] = relationship("OutfitCombo")


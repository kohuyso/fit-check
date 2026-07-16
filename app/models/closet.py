from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Bảng trung gian (Many-to-Many): Một Outfit có nhiều món đồ, một món đồ nằm trong nhiều Outfit
outfit_item_association = Table(
    "outfit_item_association",
    Base.metadata,
    Column("outfit_id", Integer, ForeignKey("outfit_combos.id", ondelete="CASCADE")),
    Column("clothing_item_id", Integer, ForeignKey("clothing_items.id", ondelete="CASCADE"))
)

class ClothingItem(Base):
    __tablename__ = "clothing_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    image_url = Column(String, nullable=False)   # Link ảnh PNG sạch nền lưu trên S3
    category = Column(String, nullable=False)    # Shirts, Pants, Shoes, Jackets (Screen 4 filter)
    color_code = Column(String, nullable=False)  # Ví dụ: #1E293B
    style_tag = Column(String, nullable=False)   # Formal, Casual
    is_favorite = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OutfitCombo(Base):
    __tablename__ = "outfit_combos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    style_type = Column(String, nullable=True)   # "Office Meeting", "Rainy Day"...
    
    # Liên kết với danh sách các món đồ nằm trong bộ này
    items = relationship("ClothingItem", secondary=outfit_item_association)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserCalendar(Base):
    __tablename__ = "user_calendar"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    outfit_combo_id = Column(Integer, ForeignKey("outfit_combos.id", ondelete="SET NULL"), nullable=True)
    
    date = Column(DateTime, nullable=False)     # Ngày xếp lịch (Screen 6)
    event_title = Column(String, nullable=True) # Ví dụ: "Office Meeting" (Screen 2)
    weather_status = Column(String, nullable=True) # Ví dụ: "Rain, 22°C"
    
    outfit = relationship("OutfitCombo")
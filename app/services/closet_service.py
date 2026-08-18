from typing import List, Dict, Any, Optional, cast
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.closet import ClothingItem
from app.services.color_math import get_color_name_from_hex

def get_user_closet_items(
    db: Session, 
    user_id: int, 
    category: Optional[str] = None, 
    search_query: Optional[str] = None
) -> List[ClothingItem]:
    """Lấy danh sách các món đồ trong tủ đồ của người dùng có hỗ trợ lọc và tìm kiếm"""
    query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
    
    if category and category.lower() != "all":
        query = query.filter(ClothingItem.category.ilike(category))
        
    if search_query:
        sq = f"%{search_query.strip()}%"
        query = query.filter(
            (ClothingItem.category.ilike(sq)) |
            (ClothingItem.style_tag.ilike(sq)) |
            (ClothingItem.color_name.ilike(sq))
        )
        
    return query.order_by(ClothingItem.id.desc()).all()

def calculate_closet_insights(db: Session, user_id: int) -> Dict[str, Any]:
    """Tính toán thống kê tủ đồ (tổng số đồ, tỉ lệ category, phong cách chủ đạo)"""
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    total_items = len(items)
    
    category_counts: Dict[str, int] = {}
    style_counts: Dict[str, int] = {}
    
    for item in items:
        cat = item.category or "Other"
        category_counts[cat] = category_counts.get(cat, 0) + 1
        
        style = item.style_tag or "Casual"
        style_counts[style] = style_counts.get(style, 0) + 1
        
    dominant_style = max(style_counts, key=lambda k: style_counts[k]) if style_counts else "Casual"
    
    return {
        "total_items": total_items,
        "category_breakdown": category_counts,
        "style_breakdown": style_counts,
        "dominant_style": dominant_style
    }

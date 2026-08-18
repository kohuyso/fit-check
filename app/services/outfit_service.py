from typing import List, Dict, Any, Optional, cast
from sqlalchemy.orm import Session
from app.models.closet import ClothingItem, OutfitCombo
from app.services.color_math import get_color_name_from_hex

def get_or_create_outfit_combo(db: Session, user_id: int, style_type: str, item_ids: List[int]) -> OutfitCombo:
    """Tìm hoặc tạo mới một OutfitCombo tránh bị trùng lặp bộ đồ giống nhau trong DB"""
    combos = db.query(OutfitCombo).filter(OutfitCombo.user_id == user_id).all()
    for combo in combos:
        existing_ids = [item.id for item in combo.items]
        if sorted(existing_ids) == sorted(item_ids):
            return combo

    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(item_ids)
    ).all()
    
    new_combo = OutfitCombo(user_id=user_id, style_type=style_type, items=items)
    db.add(new_combo)
    db.commit()
    db.refresh(new_combo)
    return new_combo

def build_outfit_recommendation_dict(
    combo: OutfitCombo,
    weather_desc: Optional[str] = None,
    weather_adjusted: bool = True
) -> Dict[str, Any]:
    """Đóng gói thông tin bộ đồ thành dict phù hợp với OutfitRecommendation schema"""
    items_list = [
        {
            "id": cast(int, item.id),
            "name": f"{item.color_name or get_color_name_from_hex(str(item.color_code))} {item.category}",
            "category": item.category,
            "color_name": item.color_name or get_color_name_from_hex(str(item.color_code)),
            "color_code": item.color_code,
            "style": item.style_tag,
            "style_tag": item.style_tag,
            "image_url": item.image_url,
            "is_ai_fixed": getattr(item, "is_ai_fixed", True)
        } for item in combo.items
    ]

    first_image = items_list[0]["image_url"] if items_list else None
    title = combo.style_type or "Curated Outfit Set"

    tags_list: List[str] = []
    for item in items_list:
        st = item.get("style_tag")
        if st and st not in tags_list:
            tags_list.append(st)
        cat = item.get("category")
        if cat and cat not in tags_list:
            tags_list.append(cat)

    if weather_desc:
        description = f"Tối ưu cho thời tiết {weather_desc}."
    else:
        description = f"Set đồ '{title}' phối hợp {len(items_list)} món trang phục chỉn chu cho ngày của bạn."

    return {
        "outfit_id": combo.id,
        "style_type": combo.style_type or "Daily Set",
        "title": title,
        "description": description,
        "image_url": first_image,
        "tags": tags_list,
        "weather_adjusted": weather_adjusted,
        "items": items_list
    }

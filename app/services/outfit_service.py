from typing import List, Dict, Any, Optional, cast
from sqlalchemy.orm import Session
from app.models.closet import ClothingItem, OutfitCombo
from app.services.color_math import get_color_name_from_hex

def get_or_create_outfit_combo(db: Session, user_id: int, style_type: str, item_ids: List[int]) -> Optional[OutfitCombo]:
    """
    Tìm hoặc tạo mới một OutfitCombo với cơ chế Guardrail:
    1. Lọc và loại bỏ các ID trùng lặp hoặc không hợp lệ.
    2. Xác thực quyền sở hữu: Tất cả items phải thuộc về user_id trong Database.
    3. Tránh tạo outfit nếu số món đồ hợp lệ < 2.
    4. Tránh tạo trùng lặp bộ đồ giống nhau trong DB.
    """
    if not item_ids:
        return None

    # Chuyển đổi và lọc các ID hợp lệ
    clean_ids: List[int] = []
    for raw_id in item_ids:
        try:
            parsed_id = int(raw_id)
            if parsed_id not in clean_ids:
                clean_ids.append(parsed_id)
        except (ValueError, TypeError):
            continue

    if len(clean_ids) < 2:
        return None

    # Lấy các món đồ thực sự thuộc quyền sở hữu của user_id
    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(clean_ids)
    ).all()

    if len(items) < 2:
        return None

    valid_item_ids = [item.id for item in items]

    # Kiểm tra xem combo với đúng tập item_ids này đã tồn tại chưa
    combos = db.query(OutfitCombo).filter(OutfitCombo.user_id == user_id).all()
    for combo in combos:
        existing_ids = [item.id for item in combo.items]
        if sorted(existing_ids) == sorted(valid_item_ids):
            return combo

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

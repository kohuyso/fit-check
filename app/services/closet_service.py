import datetime
from typing import List, Dict, Any, Optional, cast
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.closet import ClothingItem, OutfitCombo, UserCalendar, outfit_item_association
from app.schemas import closet_schema
from app.services.color_math import get_color_name_from_hex, calculate_contrast_ratio
from app.services.storage import sanitize_image_url
from app.core.logger import logger

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

def save_scanned_clothing_item(
    db: Session, 
    user_id: int, 
    item_in: closet_schema.ApproveAndSaveRequest
) -> ClothingItem:
    """Lưu món đồ đã quét AI vào cơ sở dữ liệu và kích hoạt embedding nếu có"""
    if not item_in.image_url or not item_in.image_url.strip() or not item_in.category or not item_in.category.strip() or not item_in.color_code or not item_in.color_code.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vui lòng cung cấp đầy đủ thông tin trang phục (hình ảnh, danh mục, mã màu)."
        )

    color_name = item_in.color_name or get_color_name_from_hex(item_in.color_code)
    new_clothing = ClothingItem(
        user_id=user_id,
        image_url=sanitize_image_url(item_in.image_url.strip()),
        category=item_in.category.strip(),
        color_name=color_name,
        color_code=item_in.color_code.strip(),
        style_tag=item_in.style_tag.strip() if item_in.style_tag else "Casual",
        is_ai_fixed=item_in.is_ai_fixed if item_in.is_ai_fixed is not None else True
    )
    db.add(new_clothing)
    db.commit()
    db.refresh(new_clothing)
    
    try:
        from app.services.embedding_service import compute_and_save_item_embedding
        compute_and_save_item_embedding(db, new_clothing)
    except Exception as emb_err:
        logger.warning(f"Không thể tính toán embedding cho item {new_clothing.id}: {emb_err}")
        
    return new_clothing

def get_closet_items_flat(
    db: Session,
    user_id: int,
    category: str = "All",
    style: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Truy vấn danh sách đồ phẳng kèm phân trang, lọc theo danh mục, phong cách và từ khóa"""
    skip = max(0, skip)
    limit = max(1, min(100, limit))

    query = db.query(ClothingItem).filter(ClothingItem.user_id == user_id)
    
    if category != "All":
        query = query.filter(ClothingItem.category == category)
        
    if style:
        query = query.filter(ClothingItem.style_tag == style)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ClothingItem.category.ilike(search_pattern),
                ClothingItem.style_tag.ilike(search_pattern),
                ClothingItem.color_name.ilike(search_pattern)
            )
        )
        
    items = query.offset(skip).limit(limit).all()
    
    result = []
    for i in items:
        c_name = i.color_name or get_color_name_from_hex(str(i.color_code))
        result.append({
            "id": i.id,
            "name": f"{c_name} {i.category}",
            "category": i.category,
            "color_name": c_name,
            "color_code": i.color_code,
            "style": i.style_tag,
            "style_tag": i.style_tag,
            "image_url": sanitize_image_url(i.image_url),
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        })
    return result

def get_clothing_item_detail(
    db: Session,
    user_id: int,
    item_id: int
) -> Dict[str, Any]:
    """Lấy chi tiết món đồ kèm thống kê số lần mặc và gợi ý phối màu hòa hợp"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user_id
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    color_name = item.color_name or get_color_name_from_hex(str(item.color_code))

    # 1. Đếm số lần mặc thực tế từ dữ liệu UserCalendar trong 30 ngày qua
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    worn_count = db.query(func.count(UserCalendar.id)).\
        join(OutfitCombo, UserCalendar.outfit_combo_id == OutfitCombo.id).\
        join(outfit_item_association, OutfitCombo.id == outfit_item_association.c.outfit_id).\
        filter(
            UserCalendar.user_id == user_id,
            outfit_item_association.c.clothing_item_id == item.id,
            UserCalendar.date >= thirty_days_ago
        ).scalar() or 0

    # 2. Tìm các món đồ hợp cạ bằng độ tương phản màu sắc
    other_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id != item.id
    ).all()

    matching_candidates = []
    good_match_count = 0

    for candidate in other_items:
        if candidate.category != item.category:
            ratio = calculate_contrast_ratio(str(item.color_code), str(candidate.color_code))
            if ratio >= 1.8:
                good_match_count += 1
                matching_candidates.append((ratio, candidate))

    matching_candidates.sort(key=lambda x: x[0], reverse=True)
    top_pairs = [pair[1] for pair in matching_candidates[:4]]

    pairs_well_with = [
        {
            "id": i.id,
            "name": f"{i.color_name or get_color_name_from_hex(str(i.color_code))} {i.category}",
            "category": i.category,
            "color_name": i.color_name or get_color_name_from_hex(str(i.color_code)),
            "color_code": i.color_code,
            "style": i.style_tag,
            "style_tag": i.style_tag,
            "image_url": sanitize_image_url(i.image_url),
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        } for i in top_pairs
    ]

    total_other = len(other_items)
    versatility_score = int((good_match_count / total_other) * 100) if total_other > 0 else 50

    ai_note = (
        f"Món đồ mang sắc thái {color_name} phong cách {item.style_tag}. "
        f"Dễ dàng phối cùng {len(top_pairs)} món đồ khác trong tủ để tạo nên bộ trang phục chỉn chu."
    )

    return {
        "id": item.id,
        "name": f"{color_name} {item.category}",
        "category": item.category,
        "color_name": color_name,
        "color_code": item.color_code,
        "style": item.style_tag,
        "image_url": sanitize_image_url(item.image_url),
        "stats": {
            "worn_count_this_month": worn_count,
            "versatility_score": versatility_score,
            "matching_items_count": good_match_count
        },
        "pairs_well_with": pairs_well_with,
        "ai_styling_note": ai_note
    }

def update_clothing_item_details(
    db: Session,
    user_id: int,
    item_id: int,
    item_in: closet_schema.ItemUpdateRequest
) -> Dict[str, Any]:
    """Cập nhật thông tin món đồ trong cơ sở dữ liệu"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    if item_in.category is not None:
        item.category = item_in.category.strip()
    if item_in.color_name is not None:
        item.color_name = item_in.color_name.strip()
    if item_in.color_code is not None:
        item.color_code = item_in.color_code.strip()
    if item_in.style_tag is not None:
        item.style_tag = item_in.style_tag.strip()

    db.commit()
    db.refresh(item)

    c_name = item.color_name or get_color_name_from_hex(str(item.color_code))
    return {
        "id": item.id,
        "name": item_in.name.strip() if item_in.name else f"{c_name} {item.category}",
        "category": item.category,
        "color_name": c_name,
        "color_code": item.color_code,
        "style": item.style_tag,
        "style_tag": item.style_tag,
        "image_url": sanitize_image_url(item.image_url),
        "is_ai_fixed": getattr(item, "is_ai_fixed", True)
    }

def delete_clothing_item_by_id(db: Session, user_id: int, item_id: int) -> str:
    """Xóa một món đồ khỏi tủ đồ của người dùng"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    cat_name = item.category
    db.delete(item)
    db.commit()
    return f"Đã xóa món đồ '{cat_name}' khỏi tủ đồ thành công."

def toggle_clothing_item_favorite(db: Session, user_id: int, item_id: int) -> bool:
    """Bật / Tắt trạng thái yêu thích của món đồ"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    item.is_favorite = not item.is_favorite
    db.commit()
    return bool(item.is_favorite)

def create_user_custom_outfit(
    db: Session,
    user_id: int,
    outfit_in: closet_schema.OutfitCreateRequest
) -> OutfitCombo:
    """Tạo mới bộ phối đồ thủ công từ danh sách ID món đồ"""
    if not outfit_in.item_ids or len(outfit_in.item_ids) == 0:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 món đồ để tạo bộ trang phục.")

    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(outfit_in.item_ids)
    ).all()

    if not items:
        raise HTTPException(status_code=404, detail="Không tìm thấy các món đồ được chọn.")

    new_combo = OutfitCombo(
        user_id=user_id,
        style_type=outfit_in.style_type or "Custom Outfit",
        items=items
    )
    db.add(new_combo)
    db.commit()
    db.refresh(new_combo)
    return new_combo

def get_user_outfits_list(db: Session, user_id: int, bookmarked_only: bool = False) -> List[OutfitCombo]:
    """Lấy danh sách các combo trang phục của người dùng"""
    query = db.query(OutfitCombo).filter(OutfitCombo.user_id == user_id)
    if bookmarked_only:
        query = query.filter(OutfitCombo.is_bookmarked == True)

    return query.order_by(OutfitCombo.created_at.desc()).all()

def get_user_outfit_by_id(db: Session, user_id: int, outfit_id: int) -> OutfitCombo:
    """Lấy thông tin chi tiết một bộ outfit theo ID"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == user_id
    ).first()
    if not outfit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bộ phối đồ này.")
    return outfit

def toggle_user_outfit_bookmark(db: Session, user_id: int, outfit_id: int) -> bool:
    """Bật / Tắt trạng thái bookmark của bộ phối đồ"""
    outfit = get_user_outfit_by_id(db, user_id, outfit_id)
    outfit.is_bookmarked = not outfit.is_bookmarked
    db.commit()
    return bool(outfit.is_bookmarked)

def delete_user_outfit_by_id(db: Session, user_id: int, outfit_id: int) -> None:
    """Xóa một bộ phối đồ"""
    outfit = get_user_outfit_by_id(db, user_id, outfit_id)
    db.delete(outfit)
    db.commit()

def update_user_outfit_combo(
    db: Session,
    user_id: int,
    outfit_id: int,
    outfit_in: closet_schema.OutfitUpdateRequest
) -> OutfitCombo:
    """Cập nhật phong cách hoặc danh sách món đồ trong bộ phối đồ"""
    outfit = get_user_outfit_by_id(db, user_id, outfit_id)

    if outfit_in.style_type is not None:
        outfit.style_type = outfit_in.style_type.strip()

    if outfit_in.item_ids is not None:
        items = db.query(ClothingItem).filter(
            ClothingItem.user_id == user_id,
            ClothingItem.id.in_(outfit_in.item_ids)
        ).all()
        if not items:
            raise HTTPException(status_code=400, detail="Các món đồ được chọn không tồn tại.")
        outfit.items = items

    db.commit()
    db.refresh(outfit)
    return outfit

def get_closet_summary_data(db: Session, user_id: int) -> Dict[str, Any]:
    """Tổng hợp báo cáo tổng quan tủ đồ (số lượng theo danh mục, tỷ lệ màu sắc)"""
    items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    total_items = len(items)
    favorites_count = sum(1 for i in items if i.is_favorite)

    cat_counts: Dict[str, int] = {}
    color_counts: Dict[str, Dict[str, Any]] = {}

    for i in items:
        cat = i.category
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

        c_name = i.color_name or get_color_name_from_hex(str(i.color_code))
        if c_name not in color_counts:
            color_counts[c_name] = {"color_name": c_name, "color_code": i.color_code, "count": 0}
        color_counts[c_name]["count"] += 1

    color_distribution = []
    for c_info in color_counts.values():
        percentage = round((c_info["count"] / total_items) * 100, 1) if total_items > 0 else 0.0
        color_distribution.append({
            "color_name": c_info["color_name"],
            "color_code": c_info["color_code"],
            "count": c_info["count"],
            "percentage": percentage
        })

    color_distribution.sort(key=lambda x: x["count"], reverse=True)

    return {
        "total_items": total_items,
        "favorites_count": favorites_count,
        "category_counts": cat_counts,
        "color_distribution": color_distribution
    }

def get_matching_item_pairings(db: Session, user_id: int, item_id: int) -> List[Dict[str, Any]]:
    """Gợi ý danh sách các món đồ phối hợp ăn ý nhất với 1 item cụ thể"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    other_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id != item.id
    ).all()

    matching_candidates = []
    for candidate in other_items:
        if candidate.category != item.category:
            ratio = calculate_contrast_ratio(str(item.color_code), str(candidate.color_code))
            if ratio >= 1.8:
                matching_candidates.append((ratio, candidate))

    matching_candidates.sort(key=lambda x: x[0], reverse=True)
    top_pairs = [pair[1] for pair in matching_candidates[:8]]

    result = []
    for i in top_pairs:
        c_name = i.color_name or get_color_name_from_hex(str(i.color_code))
        result.append({
            "id": i.id,
            "name": f"{c_name} {i.category}",
            "category": i.category,
            "color_name": c_name,
            "color_code": i.color_code,
            "style": i.style_tag,
            "style_tag": i.style_tag,
            "image_url": sanitize_image_url(i.image_url),
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        })

    return result

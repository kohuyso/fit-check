# app/routers/closet.py
import os
import uuid
import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_user
from app.services.ai_workers import dispatch_scan_task, celery_app
from app.schemas import closet_schema
from app.models.closet import ClothingItem, OutfitCombo, UserCalendar, outfit_item_association
from app.models.user import User
from app.core.logger import logger
from app.services.outfit_service import build_outfit_recommendation_dict
from app.services.storage import upload_image_to_s3, validate_and_get_image_extension
from app.services.color_math import get_color_name_from_hex, calculate_contrast_ratio

router = APIRouter(prefix="/api/v1/closet", tags=["Closet & AI Scanner"])

@router.post("/scan", response_model=closet_schema.ScanInitiateResponse)
@router.post("/upload", response_model=closet_schema.ScanInitiateResponse)
async def scan_clothing_camera(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """
    Bước 1: Mobile chụp ảnh gửi lên -> Đẩy ngay việc vào Queue / Thread ngầm xử lý.
    """
    ext = validate_and_get_image_extension(file)
        
    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )
    
    unique_filename = f"{uuid.uuid4()}.{ext}"

    # Luôn lưu file local vào temp_uploads để Celery worker truy cập trực tiếp
    shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp_uploads")
    os.makedirs(shared_dir, exist_ok=True)
    local_saved_path = os.path.join(shared_dir, unique_filename)
    with open(local_saved_path, "wb") as buffer:
        buffer.write(file_bytes)

    # Đẩy lên S3 dưới dạng temp file dự phòng nếu có cấu hình
    object_name = f"temp/{current_user.id}/{unique_filename}"
    s3_url = upload_image_to_s3(file_bytes, object_name)

    image_target = local_saved_path if os.path.exists(local_saved_path) else (s3_url or local_saved_path)
    task_id = dispatch_scan_task(image_target, current_user.id)
    return {"status": "queued", "task_id": task_id}

@router.get("/scan/status/{task_id}", response_model=closet_schema.TaskStatusResponse)
@router.get("/task-status/{task_id}", response_model=closet_schema.TaskStatusResponse)
def get_scan_task_status(task_id: str):
    """
    Bước 2: Mobile gọi lại API kiểm tra kết quả xử lý từ Celery AI Worker ngầm.
    """
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã task ID không được để trống."
        )

    task_result = celery_app.AsyncResult(task_id)
    
    status_str = "PENDING"
    progress_message = None
    formatted_result = None
    
    if task_result.state == 'PROGRESS':
        status_str = "PENDING"
        if isinstance(task_result.info, dict):
            progress_message = task_result.info.get('message')
    elif task_result.state == 'SUCCESS':
        status_str = "COMPLETED"
        raw_res = task_result.result if isinstance(task_result.result, dict) else {}
        detected = raw_res.get("detected_tags", {})
        color_code = detected.get("color_code", "#1E293B")
        color_name = detected.get("color_name") or get_color_name_from_hex(color_code)
        
        formatted_result = {
            "category": detected.get("category", "Shirts"),
            "color_name": color_name,
            "color_code": color_code,
            "style_tag": detected.get("style_tag", "Casual"),
            "processed_image_url": raw_res.get("processed_image_url", "")
        }
    elif task_result.state == 'FAILURE':
        status_str = "FAILED"
        progress_message = "Có lỗi xảy ra trong quá trình AI phân tích hình ảnh."
        
    return {
        "task_id": task_id,
        "status": status_str,
        "state": task_result.state,
        "progress_message": progress_message,
        "result": formatted_result
    }

@router.post("/save", status_code=status.HTTP_201_CREATED)
def approve_and_save_item(item_in: closet_schema.ApproveAndSaveRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Bước 3: User bấm "Approve & Save". Backend lưu vào PostgreSQL.
    """
    if not item_in.image_url or not item_in.image_url.strip() or not item_in.category or not item_in.category.strip() or not item_in.color_code or not item_in.color_code.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vui lòng cung cấp đầy đủ thông tin trang phục (hình ảnh, danh mục, mã màu)."
        )

    color_name = item_in.color_name or get_color_name_from_hex(item_in.color_code)
    new_clothing = ClothingItem(
        user_id=current_user.id,
        image_url=item_in.image_url.strip(),
        category=item_in.category.strip(),
        color_name=color_name,
        color_code=item_in.color_code.strip(),
        style_tag=item_in.style_tag.strip() if item_in.style_tag else "Casual",
        is_ai_fixed=item_in.is_ai_fixed if item_in.is_ai_fixed is not None else True
    )
    db.add(new_clothing)
    db.commit()
    db.refresh(new_clothing)
    
    # Tự động tính toán và lưu Vector Embedding cho RAG
    try:
        from app.services.embedding_service import compute_and_save_item_embedding
        compute_and_save_item_embedding(db, new_clothing)
    except Exception as emb_err:
        logger.warning(f"Không thể tính toán embedding cho item {new_clothing.id}: {emb_err}")
        
    return {"status": "success", "message": "Đã lưu trang phục thành công vào tủ đồ ảo của bạn!", "item_id": new_clothing.id}

@router.get("/items", response_model=List[closet_schema.ClothingItemFlat])
def get_my_wardrobe(
    category: str = "All",
    style: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API lấy toàn bộ tủ đồ phẳng, hỗ trợ filter và search linh hoạt"""
    skip = max(0, skip)
    limit = max(1, min(100, limit))

    query = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id)
    
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
            "image_url": i.image_url,
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        })
    return result

@router.get("/items/{item_id}", response_model=closet_schema.ClothingItemDetailResponse)
def get_item_detail(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Lấy chi tiết 1 món đồ trong tủ với các chỉ số thống kê thực tế từ DB và thuật toán phối màu.
    """
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == current_user.id
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
            UserCalendar.user_id == current_user.id,
            outfit_item_association.c.clothing_item_id == item.id,
            UserCalendar.date >= thirty_days_ago
        ).scalar() or 0

    # 2. Tìm các món đồ hợp cạ thực sự bằng thuật toán tính độ tương phản sắc thái (WCAG Color Contrast)
    other_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == current_user.id,
        ClothingItem.id != item.id
    ).all()

    matching_candidates = []
    good_match_count = 0

    for candidate in other_items:
        # Ưu tiên món đồ thuộc danh mục khác nhau
        if candidate.category != item.category:
            ratio = calculate_contrast_ratio(str(item.color_code), str(candidate.color_code))
            # Tỷ lệ tương phản từ 1.8 trở lên được coi là phối màu hài hòa
            if ratio >= 1.8:
                good_match_count += 1
                matching_candidates.append((ratio, candidate))

    # Sắp xếp các món đồ có tỉ lệ hợp nhất lên đầu
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
            "image_url": i.image_url,
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        } for i in top_pairs
    ]

    total_other = len(other_items)
    versatility_score = int((good_match_count / total_other) * 100) if total_other > 0 else 50

    # 3. Tạo câu tư vấn AI linh hoạt dựa theo đặc tính món đồ thực tế
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
        "image_url": item.image_url,
        "stats": {
            "worn_count_this_month": worn_count,
            "versatility_score": versatility_score,
            "matching_items_count": good_match_count
        },
        "pairs_well_with": pairs_well_with,
        "ai_styling_note": ai_note
    }

@router.put("/items/{item_id}", response_model=closet_schema.ClothingItemFlat)
def update_clothing_item(
    item_id: int,
    item_in: closet_schema.ItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Cập nhật thông tin món đồ (danh mục, màu sắc, phong cách, tên)"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == current_user.id
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
        "image_url": item.image_url,
        "is_ai_fixed": getattr(item, "is_ai_fixed", True)
    }

@router.delete("/items/{item_id}")
def delete_clothing_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa 1 món đồ khỏi tủ đồ"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    db.delete(item)
    db.commit()
    return {"status": "success", "message": f"Đã xóa món đồ '{item.category}' khỏi tủ đồ thành công."}

@router.post("/items/{item_id}/favorite")
def toggle_favorite_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Bật/Tắt trạng thái yêu thích món đồ"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    item.is_favorite = not item.is_favorite
    db.commit()
    return {"status": "success", "is_favorite": item.is_favorite, "message": "Đã cập nhật trạng thái yêu thích."}

@router.post("/outfits", response_model=closet_schema.OutfitRecommendation, status_code=status.HTTP_201_CREATED)
def create_custom_outfit(
    outfit_in: closet_schema.OutfitCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Tạo và lưu bộ phối đồ ghép thủ công từ các item IDs"""
    if not outfit_in.item_ids or len(outfit_in.item_ids) == 0:
        raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 món đồ để tạo bộ trang phục.")

    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == current_user.id,
        ClothingItem.id.in_(outfit_in.item_ids)
    ).all()

    if not items:
        raise HTTPException(status_code=404, detail="Không tìm thấy các món đồ được chọn.")

    new_combo = OutfitCombo(
        user_id=current_user.id,
        style_type=outfit_in.style_type or "Custom Outfit",
        items=items
    )
    db.add(new_combo)
    db.commit()
    db.refresh(new_combo)

    return build_outfit_recommendation_dict(new_combo)

@router.get("/outfits", response_model=List[closet_schema.OutfitRecommendation])
def get_my_outfits(
    bookmarked_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy danh sách toàn bộ các outfit combos của người dùng"""
    query = db.query(OutfitCombo).filter(OutfitCombo.user_id == current_user.id)
    if bookmarked_only:
        query = query.filter(OutfitCombo.is_bookmarked == True)

    combos = query.order_by(OutfitCombo.created_at.desc()).all()

    return [build_outfit_recommendation_dict(combo) for combo in combos]

@router.get("/outfits/{outfit_id}", response_model=closet_schema.OutfitRecommendation)
def get_outfit_detail(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xem chi tiết 1 outfit riêng biệt kèm danh sách món đồ (ClothingItemFlat)"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bộ phối đồ này.")

    return build_outfit_recommendation_dict(outfit)

@router.post("/outfits/{outfit_id}/bookmark")
def toggle_bookmark_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Bookmark/Lưu bộ outfit gợi ý vào danh sách yêu thích"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ phối đồ này.")

    outfit.is_bookmarked = not outfit.is_bookmarked
    db.commit()
    return {"status": "success", "is_bookmarked": outfit.is_bookmarked, "message": "Đã cập nhật trạng thái bookmark outfit."}

@router.delete("/outfits/{outfit_id}")
def delete_custom_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa một set phối đồ (Outfit) khỏi danh sách cá nhân"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ phối đồ này.")

    db.delete(outfit)
    db.commit()
    return {"status": "success", "message": "Đã xóa bộ phối đồ thành công."}

@router.put("/outfits/{outfit_id}", response_model=closet_schema.OutfitRecommendation)
def update_custom_outfit(
    outfit_id: int,
    outfit_in: closet_schema.OutfitUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Cập nhật danh sách món đồ hoặc phong cách của một Outfit đã tạo"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ phối đồ này.")

    if outfit_in.style_type is not None:
        outfit.style_type = outfit_in.style_type.strip()

    if outfit_in.item_ids is not None:
        items = db.query(ClothingItem).filter(
            ClothingItem.user_id == current_user.id,
            ClothingItem.id.in_(outfit_in.item_ids)
        ).all()
        if not items:
            raise HTTPException(status_code=400, detail="Các món đồ được chọn không tồn tại.")
        outfit.items = items

    db.commit()
    db.refresh(outfit)

    return build_outfit_recommendation_dict(outfit)

@router.post("/items/upload")
async def upload_clothing_item_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """API Upload trực tiếp file ảnh chụp món đồ từ thiết bị di động"""
    ext = validate_and_get_image_extension(file)

    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )

    unique_filename = f"{uuid.uuid4()}.{ext}"
    object_name = f"items/{current_user.id}/{unique_filename}"
    s3_url = upload_image_to_s3(file_bytes, object_name)

    image_target = s3_url
    if not image_target:
        shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp_uploads")
        os.makedirs(shared_dir, exist_ok=True)
        mock_saved_path = os.path.join(shared_dir, unique_filename)
        with open(mock_saved_path, "wb") as buffer:
            buffer.write(file_bytes)
        image_target = mock_saved_path

    return {"status": "success", "image_url": image_target}

@router.get("/summary", response_model=closet_schema.ClosetSummaryResponse)
def get_closet_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy báo cáo tổng quan tủ đồ (Số lượng theo từng danh mục & tỷ lệ màu sắc)"""
    items = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id).all()
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

@router.get("/items/{item_id}/pairings", response_model=List[closet_schema.ClothingItemFlat])
def get_item_pairings(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Trả về danh sách các món đồ phối hợp ăn ý nhất với 1 item cụ thể dựa trên Color Theory"""
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.id != None,
        ClothingItem.user_id == current_user.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ này trong tủ của bạn.")

    other_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == current_user.id,
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
            "image_url": i.image_url,
            "is_ai_fixed": getattr(i, "is_ai_fixed", True)
        })

    return result
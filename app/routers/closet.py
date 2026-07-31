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
from app.services.storage import upload_image_to_s3
from app.services.color_math import get_color_name_from_hex, calculate_contrast_ratio

router = APIRouter(prefix="/api/v1/closet", tags=["Closet & AI Scanner"])

@router.post("/scan", response_model=closet_schema.ScanInitiateResponse)
async def scan_clothing_camera(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """
    Bước 1: Mobile chụp ảnh gửi lên -> Đẩy ngay việc vào Queue / Thread ngầm xử lý.
    """
    if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận file ảnh định dạng PNG, JPG, JPEG hoặc WEBP."
        )
        
    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )
    
    ext = file.filename.split('.')[-1] if file.filename else 'png'
    unique_filename = f"{uuid.uuid4()}.{ext}"
    object_name = f"temp/{current_user.id}/{unique_filename}"
    s3_url = upload_image_to_s3(file_bytes, object_name)
    
    image_target = s3_url
    if not image_target:
        shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "temp_uploads")
        os.makedirs(shared_dir, exist_ok=True)
        mock_saved_path = os.path.join(shared_dir, unique_filename)
        with open(mock_saved_path, "wb") as buffer:
            buffer.write(file_bytes)
        image_target = mock_saved_path

    task_id = dispatch_scan_task(image_target, current_user.id)
    return {"status": "queued", "task_id": task_id}

@router.get("/scan/status/{task_id}", response_model=closet_schema.TaskStatusResponse)
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
    return {"status": "success", "message": "Đã lưu trang phục thành công vào tủ đồ ảo của bạn!"}

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
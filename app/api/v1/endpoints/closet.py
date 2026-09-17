import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas import closet_schema
from app.services import closet_service
from app.services.ai_workers import dispatch_scan_task, celery_app
from app.services.outfit_service import build_outfit_recommendation_dict
from app.services.storage import upload_image_to_s3, validate_and_get_image_extension
from app.services.color_math import get_color_name_from_hex

router = APIRouter()

@router.post("/scan", response_model=closet_schema.ScanInitiateResponse)
@router.post("/upload", response_model=closet_schema.ScanInitiateResponse)
@limiter.limit("10/minute")
async def scan_clothing_camera(request: Request, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Bước 1: Mobile chụp ảnh gửi lên -> Đẩy ngay việc vào Celery Queue ngầm xử lý"""
    ext = validate_and_get_image_extension(file)

        
    file_bytes = await file.read()
    if not file_bytes or len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ảnh tải lên rỗng, vui lòng chọn file ảnh hợp lệ."
        )
    
    unique_filename = f"{uuid.uuid4()}.{ext}"

    # Luôn lưu file local vào temp_uploads để Celery worker truy cập trực tiếp
    shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "temp_uploads")
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
    """Bước 2: Mobile gọi lại API kiểm tra kết quả xử lý từ Celery AI Worker ngầm"""
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
def approve_and_save_item(
    item_in: closet_schema.ApproveAndSaveRequest, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Bước 3: User bấm 'Approve & Save' -> Lưu vào DB và kích hoạt RAG Embedding"""
    new_clothing = closet_service.save_scanned_clothing_item(
        db=db, 
        user_id=current_user.id, 
        item_in=item_in
    )
    return {
        "status": "success", 
        "message": "Đã lưu trang phục thành công vào tủ đồ ảo của bạn!", 
        "item_id": new_clothing.id
    }

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
    return closet_service.get_closet_items_flat(
        db=db,
        user_id=current_user.id,
        category=category,
        style=style,
        search=search,
        skip=skip,
        limit=limit
    )

@router.get("/items/{item_id}", response_model=closet_schema.ClothingItemDetailResponse)
def get_item_detail(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy chi tiết 1 món đồ trong tủ với các chỉ số thống kê thực tế và gợi ý phối màu"""
    return closet_service.get_clothing_item_detail(
        db=db,
        user_id=current_user.id,
        item_id=item_id
    )

@router.put("/items/{item_id}", response_model=closet_schema.ClothingItemFlat)
def update_clothing_item(
    item_id: int,
    item_in: closet_schema.ItemUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Cập nhật thông tin món đồ (danh mục, màu sắc, phong cách, tên)"""
    return closet_service.update_clothing_item_details(
        db=db,
        user_id=current_user.id,
        item_id=item_id,
        item_in=item_in
    )

@router.delete("/items/{item_id}")
def delete_clothing_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa 1 món đồ khỏi tủ đồ"""
    msg = closet_service.delete_clothing_item_by_id(
        db=db,
        user_id=current_user.id,
        item_id=item_id
    )
    return {"status": "success", "message": msg}

@router.post("/items/{item_id}/favorite")
def toggle_favorite_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Bật/Tắt trạng thái yêu thích món đồ"""
    is_favorite = closet_service.toggle_clothing_item_favorite(
        db=db,
        user_id=current_user.id,
        item_id=item_id
    )
    return {
        "status": "success", 
        "is_favorite": is_favorite, 
        "message": "Đã cập nhật trạng thái yêu thích."
    }

@router.post("/outfits", response_model=closet_schema.OutfitRecommendation, status_code=status.HTTP_201_CREATED)
def create_custom_outfit(
    outfit_in: closet_schema.OutfitCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Tạo và lưu bộ phối đồ ghép thủ công từ các item IDs"""
    new_combo = closet_service.create_user_custom_outfit(
        db=db,
        user_id=current_user.id,
        outfit_in=outfit_in
    )
    return build_outfit_recommendation_dict(new_combo)

@router.get("/outfits", response_model=List[closet_schema.OutfitRecommendation])
def get_my_outfits(
    bookmarked_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy danh sách toàn bộ các outfit combos của người dùng"""
    combos = closet_service.get_user_outfits_list(
        db=db,
        user_id=current_user.id,
        bookmarked_only=bookmarked_only
    )
    return [build_outfit_recommendation_dict(combo) for combo in combos]

@router.get("/outfits/{outfit_id}", response_model=closet_schema.OutfitRecommendation)
def get_outfit_detail(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xem chi tiết 1 outfit riêng biệt kèm danh sách món đồ (ClothingItemFlat)"""
    outfit = closet_service.get_user_outfit_by_id(
        db=db,
        user_id=current_user.id,
        outfit_id=outfit_id
    )
    return build_outfit_recommendation_dict(outfit)

@router.post("/outfits/{outfit_id}/bookmark")
def toggle_bookmark_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Bookmark/Lưu bộ outfit gợi ý vào danh sách yêu thích"""
    is_bookmarked = closet_service.toggle_user_outfit_bookmark(
        db=db,
        user_id=current_user.id,
        outfit_id=outfit_id
    )
    return {
        "status": "success", 
        "is_bookmarked": is_bookmarked, 
        "message": "Đã cập nhật trạng thái bookmark outfit."
    }

@router.delete("/outfits/{outfit_id}")
def delete_custom_outfit(
    outfit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa một set phối đồ (Outfit) khỏi danh sách cá nhân"""
    closet_service.delete_user_outfit_by_id(
        db=db,
        user_id=current_user.id,
        outfit_id=outfit_id
    )
    return {"status": "success", "message": "Đã xóa bộ phối đồ thành công."}

@router.put("/outfits/{outfit_id}", response_model=closet_schema.OutfitRecommendation)
def update_custom_outfit(
    outfit_id: int,
    outfit_in: closet_schema.OutfitUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Cập nhật danh sách món đồ hoặc phong cách của một Outfit đã tạo"""
    outfit = closet_service.update_user_outfit_combo(
        db=db,
        user_id=current_user.id,
        outfit_id=outfit_id,
        outfit_in=outfit_in
    )
    return build_outfit_recommendation_dict(outfit)

@router.post("/items/upload")
@limiter.limit("10/minute")
async def upload_clothing_item_image(
    request: Request,
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
        shared_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "temp_uploads")
        os.makedirs(shared_dir, exist_ok=True)
        local_saved_path = os.path.join(shared_dir, unique_filename)
        with open(local_saved_path, "wb") as buffer:
            buffer.write(file_bytes)
        image_target = f"/temp_uploads/{unique_filename}"

    return {"status": "success", "image_url": image_target}


@router.get("/summary", response_model=closet_schema.ClosetSummaryResponse)
def get_closet_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy báo cáo tổng quan tủ đồ (Số lượng theo từng danh mục & tỷ lệ màu sắc)"""
    return closet_service.get_closet_summary_data(
        db=db,
        user_id=current_user.id
    )

@router.get("/items/{item_id}/pairings", response_model=List[closet_schema.ClothingItemFlat])
def get_item_pairings(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Trả về danh sách các món đồ phối hợp ăn ý nhất với 1 item cụ thể dựa trên Color Theory"""
    return closet_service.get_matching_item_pairings(
        db=db,
        user_id=current_user.id,
        item_id=item_id
    )

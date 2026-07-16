# app/routers/closet.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.services.ai_workers import process_clothing_image_task, celery_app
from app.schemas import closet_schema
from app.models.closet import ClothingItem
from typing import Any, Dict, List

router = APIRouter(prefix="/api/v1/closet", tags=["Closet & AI Scanner"])

@router.post("/scan", response_model=closet_schema.ScanInitiateResponse)
async def scan_clothing_camera(file: UploadFile = File(...), current_user = Depends(get_current_user)):
    """
    Bước 1: Mobile chụp ảnh gửi lên -> Đẩy ngay việc vào Redis Queue cho Worker xử lý ngầm.
    Phản hồi ngay lập tức sau vài mili-giây để Mobile hiển thị hiệu ứng quét techy.
    """
    if not file.filename or not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file ảnh định dạng PNG hoặc JPG.")
        
    # Trong thực tế: Bạn lưu file tạm vào đĩa cứng hoặc đẩy thẳng link ảnh gốc lên S3 temporary bucket
    mock_saved_path = f"/tmp/{file.filename}"
    
    # Kích hoạt Celery Task chạy ngầm bằng lệnh .delay()
    task = process_clothing_image_task.delay(mock_saved_path, current_user.id)
    
    return {"status": "queued", "task_id": task.id}

@router.get("/scan/status/{task_id}", response_model=closet_schema.TaskStatusResponse)
def get_scan_task_status(task_id: str):
    """
    Bước 2: Mobile thỉnh thoảng gọi lại API này (cứ 1 giây/lần) để kiểm tra xem AI chạy xong chưa.
    """
    task_result = celery_app.AsyncResult(task_id)
    
    response: Dict[str, Any] = {
        "task_id": task_id,
        "state": task_result.state,
        "progress_message": None,
        "result": None
    }
    
    if task_result.state == 'PROGRESS':
        response["progress_message"] = task_result.info.get('message')
    elif task_result.state == 'SUCCESS':
        response["result"] = task_result.result
    elif task_result.state == 'FAILURE':
        response["progress_message"] = "Có lỗi xảy ra trong quá trình AI phân tích hình ảnh."
        
    return response

@router.post("/save", status_code=status.HTTP_201_CREATED)
def approve_and_save_item(item_in: closet_schema.ApproveAndSaveRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Bước 3: User nhìn thấy các tag gợi ý trên màn hình Bottom 1/3, bấm "Approve & Save".
    Backend chính thức lưu món đồ sạch nền này vào tủ đồ Postgres.
    """
    new_clothing = ClothingItem(
        user_id=current_user.id,
        image_url=item_in.image_url,
        category=item_in.category,
        color_code=item_in.color_code,
        style_tag=item_in.style_tag
    )
    db.add(new_clothing)
    db.commit()
    return {"status": "success", "message": "Đã lưu trang phục thành công vào tủ đồ ảo của bạn!"}

@router.get("/items", response_model=List[closet_schema.ClothingItemFlat])
def get_my_wardrobe(category: str = "All", db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """API cho Screen 4 (My Wardrobe Screen): Lấy toàn bộ tủ đồ phẳng, hỗ trợ filter pill"""
    query = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id)
    
    if category != "All":
        query = query.filter(ClothingItem.category == category)
        
    items = query.all()
    
    # Map sang cấu trúc dữ liệu phẳng cho Mobile
    return [
        {
            "id": i.id,
            "name": f"{i.style_tag} {i.category}",
            "category": i.category,
            "image_url": i.image_url,
            "color_code": i.color_code,
            "style_tag": i.style_tag
        } for i in items
    ]
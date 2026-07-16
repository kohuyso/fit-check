# app/schemas/closet_schema.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class ClothingItemFlat(BaseModel):
    id: int
    name: str  # Tên ghép từ Category + Màu (Ví dụ: Navy Blazer)
    category: str
    image_url: str
    color_code: str
    style_tag: str

    class Config:
        from_attributes = True

class OutfitRecommendation(BaseModel):
    outfit_id: int
    style_type: str
    items: List[ClothingItemFlat]

class WeatherBlock(BaseModel):
    condition: str
    temperature: int
    recommendation: str

class DashboardResponse(BaseModel):
    location: str
    weather: WeatherBlock
    schedule: str
    recommended_outfits: List[OutfitRecommendation]

# Bổ sung vào app/schemas/closet_schema.py

class ScanInitiateResponse(BaseModel):
    status: str
    task_id: str  # Mobile sẽ dùng ID này để kéo (Poll) trạng thái kết quả

class TaskStatusResponse(BaseModel):
    task_id: str
    state: str    # PENDING, PROGRESS, SUCCESS, FAILURE
    progress_message: Optional[str] = None
    result: Optional[dict] = None  # Sẽ có data khi trạng thái là SUCCESS

class ApproveAndSaveRequest(BaseModel):
    image_url: str
    category: str
    color_code: str
    style_tag: str


class CalendarDayPreview(BaseModel):
    date: date
    day_name: str         # Mon, Tue, Wed...
    is_highlighted: bool  # Đánh dấu ngày hiện tại (Active State)
    event_title: Optional[str] = None
    outfit: Optional[OutfitRecommendation] = None

class StyleInsightsResponse(BaseModel):
    utilization_rate: int   # Phần trăm hiển thị trên Ring Chart (Ví dụ: 78)
    total_items: int        # Tổng số đồ trong tủ
    items_worn_this_month: int # Số món đã mặc ít nhất 1 lần trong tháng
    top_style: str          # Phong cách mặc nhiều nhất (Formal/Casual)


class OfflineSyncRequest(BaseModel):
    outfit_id: int
    event_title: Optional[str] = "Office Meeting"
    local_timestamp: datetime  # Thời gian user bấm nút dưới máy họ khi mất mạng

    class Config:
        from_attributes = True
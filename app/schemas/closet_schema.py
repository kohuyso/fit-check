# app/schemas/closet_schema.py
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import date, datetime

class ClothingItemFlat(BaseModel):
    id: int
    name: str  # Tên ghép từ Category + Màu (Ví dụ: Linen Shirt)
    category: str
    color_name: Optional[str] = None   # 🟢 Tên màu hiển thị (ví dụ: White, Navy Blue)
    color_code: str                    # Mã hex để vẽ chấm màu UI
    style: Optional[str] = None        # 🟢 Formal / Casual
    style_tag: Optional[str] = None    # Alias cho style
    image_url: str
    is_ai_fixed: Optional[bool] = True # 🟢 Đã qua xử lý AI tách nền hay chưa

    class Config:
        from_attributes = True

class ClothingItemDetailStats(BaseModel):
    worn_count_this_month: int
    versatility_score: int
    matching_items_count: int

class ClothingItemDetailResponse(BaseModel):
    id: int
    name: str
    category: str
    color_name: Optional[str] = None
    color_code: str
    style: str
    image_url: str
    stats: ClothingItemDetailStats
    pairs_well_with: List[ClothingItemFlat]
    ai_styling_note: str

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

class ScanInitiateResponse(BaseModel):
    status: str
    task_id: str  # Mobile sẽ dùng ID này để kéo (Poll) trạng thái kết quả

class TaskStatusResponse(BaseModel):
    task_id: str
    status: Optional[str] = "PENDING" # 🟢 Chuẩn hóa status: PENDING / COMPLETED / FAILED
    state: str                       # PENDING, PROGRESS, SUCCESS, FAILURE
    progress_message: Optional[str] = None
    result: Optional[dict] = None     # Trả về category, color_name, color_code, style_tag, processed_image_url khi SUCCESS

class ApproveAndSaveRequest(BaseModel):
    image_url: str
    category: str
    color_name: Optional[str] = None
    color_code: str
    style_tag: str
    is_ai_fixed: Optional[bool] = True

class CalendarDayPreview(BaseModel):
    date: date
    day_name: str         # Mon, Tue, Wed...
    is_highlighted: bool  # Đánh dấu ngày hiện tại (Active State)
    event_title: Optional[str] = None
    outfit: Optional[OutfitRecommendation] = None

class StyleInsightsResponse(BaseModel):
    utilization_rate: int      # Phần trăm hiển thị trên Ring Chart (Ví dụ: 78)
    total_items: int           # Tổng số đồ trong tủ
    items_worn_this_month: int # Số món đã mặc ít nhất 1 lần trong tháng
    top_style: str             # Phong cách mặc nhiều nhất (Formal/Casual)

class CalendarForecastDay(BaseModel):
    date: str
    temp_c: int
    condition: str
    icon: str

class UnwornItemsInsight(BaseModel):
    count: int
    threshold_days: int
    message: str

class WeatherImpact(BaseModel):
    level: str
    recommendation_summary: str

class CalendarInsightsResponse(BaseModel):
    utilization_rate: int
    unworn_items_insight: UnwornItemsInsight
    next_3_days_forecast: List[CalendarForecastDay]
    weather_impact: WeatherImpact

class OfflineSyncRequest(BaseModel):
    outfit_id: int
    event_title: Optional[str] = "Office Meeting"
    local_timestamp: datetime

    class Config:
        from_attributes = True

# --- AI New Features Schemas ---

class LookItem(BaseModel):
    name: str
    description: str
    occasion: str

class StyleSuggestionResponse(BaseModel):
    preferred_style: List[str]
    style_analysis: str
    style_tips: List[str]
    recommended_looks: List[LookItem]
    suggested_additions: List[str]

class OutfitFromItemsRequest(BaseModel):
    item_ids: List[int]
    event: Optional[str] = "Daily Match"
    weather: Optional[str] = "Normal"

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    image_url: Optional[str] = None

class AIChatRequest(BaseModel):
    message: str
    image_url: Optional[str] = None
    history: Optional[List[ChatMessage]] = []
    current_outfit_id: Optional[int] = None
    event: Optional[str] = "Daily Match"
    weather: Optional[str] = "Normal"

class AIChatResponse(BaseModel):
    reply: str
    reply_text: Optional[str] = None
    suggested_outfit: Optional[OutfitRecommendation] = None
    recommended_outfit: Optional[Dict[str, Any]] = None

# --- P2 Explore Schemas ---

class TrendArticle(BaseModel):
    id: int
    title: str
    season: str
    read_time: str
    image_url: str
    content: str
    tags: List[str]

class ExploreTrendsResponse(BaseModel):
    season_lookbooks: List[Dict[str, Any]]
    trend_articles: List[TrendArticle]

class ColorHarmonyGuide(BaseModel):
    harmony_type: str
    description: str
    color_wheel_tip: str
    recommended_combinations: List[Dict[str, Any]]

class ColorTheoryResponse(BaseModel):
    guides: List[ColorHarmonyGuide]
    ai_advice: str
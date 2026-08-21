# app/routers/dashboard.py
import datetime
import os
from typing import List, cast
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_user
from app.models.closet import ClothingItem, OutfitCombo, UserCalendar, outfit_item_association
from app.models.user import User
from app.schemas import closet_schema
from app.schemas.closet_schema import CalendarDayPreview, StyleInsightsResponse, OfflineSyncRequest, CalendarInsightsResponse
from app.services import weather
from app.services.ai_engine import generate_outfits, get_ai_config
from app.services.color_math import get_color_name_from_hex
from app.services.outfit_service import get_or_create_outfit_combo, build_outfit_recommendation_dict

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard & Recommendation"])

@router.get("/home", response_model=closet_schema.DashboardResponse)
async def get_home_dashboard(lat: float, lon: float, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """API chính cho Màn hình 2 - Dashboard"""
    if current_user.id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên làm việc không hợp lệ.")
        
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tọa độ vị trí (lat, lon) không hợp lệ."
        )
    user_id = cast(int, current_user.id)

    # 1. Lấy thời tiết (Có áp dụng Redis Cache bên trong)
    weather_data = await weather.get_weather_by_coords(lat, lon)
    
    # 2. Định dạng lịch trình từ DB (nếu có lịch hôm nay) hoặc mặc định
    today_date = datetime.date.today()
    today_entry = db.query(UserCalendar).filter(
        UserCalendar.user_id == user_id,
        func.date(UserCalendar.date) == today_date
    ).first()
    
    if today_entry and today_entry.event_title:
        today_schedule = f"Today's Schedule: {today_entry.event_title}"
    else:
        today_schedule = "Today's Schedule: Office Meeting"

    
    # 3. Thuật toán gợi ý Outfit (Query từ chính tủ đồ của User)
    user_items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    
    recommendations = []
    api_key, _, _, _ = get_ai_config()
    ai_success = False
    
    # Gọi AI sinh set phối đồ thực sự nếu có cấu hình LLM API Key (Gemini / OpenAI)
    if api_key and len(user_items) >= 2:
        try:
            weather_desc = weather_data.get("text", "Trời bình thường")
            raw_combos = await generate_outfits(
                user_id=user_id,
                weather=weather_desc,
                event=today_schedule,
                closet_items=user_items
            )
            
            if raw_combos and isinstance(raw_combos, list):
                for raw_combo in raw_combos:
                    style_type = raw_combo.get("style_type", "AI Recommended Outfit")
                    item_ids = raw_combo.get("items_ids", [])
                    if item_ids:
                        combo_db = get_or_create_outfit_combo(db, user_id, style_type, [int(x) for x in item_ids])
                        if combo_db:
                            recommendations.append(build_outfit_recommendation_dict(combo_db, weather_desc=weather_data.get("text")))
                if recommendations:
                    ai_success = True
        except Exception:
            ai_success = False

    # Thuật toán fallback cục bộ nếu không dùng OpenAI / gọi OpenAI lỗi
    if not ai_success:
        formal_items = [i for i in user_items if i.style_tag == "Formal"]
        source_items = formal_items if formal_items else user_items
        
        # Nhóm đồ theo loại để gợi ý
        shirts = [i for i in source_items if i.category.lower() in ("shirts", "shirt")]
        pants = [i for i in source_items if i.category.lower() in ("pants", "pant")]
        shoes = [i for i in source_items if i.category.lower() in ("shoes", "shoe")]
        jackets = [i for i in source_items if i.category.lower() in ("jackets", "jacket")]
        
        if len(user_items) >= 2:
            num_combos = 3
            for i in range(num_combos):
                combo_items = []
                if shirts:
                    combo_items.append(shirts[i % len(shirts)])
                if pants:
                    combo_items.append(pants[i % len(pants)])
                if shoes:
                    combo_items.append(shoes[i % len(shoes)])
                if jackets and ("rain" in weather_data.get("condition", "").lower() or "mưa" in weather_data.get("text", "").lower()):
                    combo_items.append(jackets[i % len(jackets)])
                
                # Bù thêm đồ để set có ít nhất 2 món
                if len(combo_items) < 2:
                    for item in source_items:
                        if item not in combo_items:
                            combo_items.append(item)
                            if len(combo_items) >= 2:
                                break
                                
                style_type = "Formal Meeting Set" if formal_items else "Daily Match Set"
                item_ids = [cast(int, item.id) for item in combo_items if item.id is not None]
                combo_db = get_or_create_outfit_combo(db, user_id, f"{style_type} Option {i+1}", item_ids)
                
                recommendations.append(build_outfit_recommendation_dict(combo_db, weather_desc=weather_data.get("text")))

    return {
        "location": "Hanoi, VN",
        "weather": {
            "condition": weather_data["condition"],
            "temperature": weather_data["temp"],
            "recommendation": weather_data["text"]
        },
        "schedule": today_schedule,
        "recommended_outfits": recommendations
    }

@router.post("/wear-outfit")
def wear_outfit(
    outfit_id: int, 
    event_title: str = "Daily Match",
    weather_status: str = "Normal",
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Bấm 'Wear This Outfit' -> Lưu vào lịch sử đồ mặc trong ngày (Screen 6)"""
    # Xác thực outfit có tồn tại và thuộc về user
    outfit = db.query(OutfitCombo).filter(OutfitCombo.id == outfit_id, OutfitCombo.user_id == current_user.id).first()
    if not outfit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy bộ phối trang phục này."
        )

    new_history = UserCalendar(
        user_id=current_user.id,
        outfit_combo_id=outfit_id,
        date=datetime.datetime.utcnow(),
        event_title=event_title,
        weather_status=weather_status
    )
    db.add(new_history)
    db.commit()
    return {"status": "success", "message": "Outfit saved to history. Have a great day!"}

CATEGORY_ALIAS_MAP = {
    "footwear": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay", "Boots", "Heels", "Sneakers"],
    "shoes": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay", "Boots", "Heels", "Sneakers"],
    "shoe": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay", "Boots", "Heels", "Sneakers"],
    "shirts": ["Shirts", "shirts", "shirt", "Shirt", "ao", "T-Shirts", "Tee", "Blouse", "Polo"],
    "shirt": ["Shirts", "shirts", "shirt", "Shirt", "ao", "T-Shirts", "Tee", "Blouse", "Polo"],
    "t-shirts": ["T-Shirts", "t-shirts", "T-shirt", "Tee", "ao-thun", "Shirts"],
    "pants": ["Pants", "pants", "pant", "Pant", "quan", "Jeans", "Trousers", "Slacks"],
    "pant": ["Pants", "pants", "pant", "Pant", "quan", "Jeans", "Trousers", "Slacks"],
    "shorts": ["Shorts", "shorts", "Short", "quan dui", "quan short", "Bermuda"],
    "jackets": ["Jackets", "jackets", "jacket", "Jacket", "ao khoac", "Coats", "Hoodies", "Blazers"],
    "jacket": ["Jackets", "jackets", "jacket", "Jacket", "ao khoac", "Coats", "Hoodies", "Blazers"],
    "dresses": ["Dresses", "dresses", "dress", "Dress", "dam", "vay", "ao dai", "aodai", "Gown"],
    "dress": ["Dresses", "dresses", "dress", "Dress", "dam", "vay", "ao dai", "aodai", "Gown"],
    "skirts": ["Skirts", "skirts", "skirt", "Skirt", "chan vay"],
    "skirt": ["Skirts", "skirts", "skirt", "Skirt", "chan vay"],
    "accessories": ["Accessories", "accessories", "accessory", "phu kien", "Bags", "Hat", "Belts", "Tui"],
    "bags": ["Bags", "bags", "bag", "Bag", "tui", "tui xach", "Accessories"],
}

@router.get("/swap-alternatives", response_model=list[closet_schema.ClothingItemFlat])
def get_swap_alternatives(category: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """API cho Screen 3 - Slide-up Bottom Sheet chọn đồ thay thế phù hợp thời tiết"""
    if not category or not category.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh mục trang phục không được để trống."
        )

    cat_lower = category.lower().strip()
    target_categories = CATEGORY_ALIAS_MAP.get(cat_lower, [category, cat_lower.capitalize(), cat_lower])

    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == current_user.id,
        or_(
            ClothingItem.category.in_(target_categories),
            ClothingItem.category.ilike(f"%{cat_lower}%")
        )
    ).limit(5).all()

    # Fallback to any user clothing items if no specific category match
    if not items:
        items = db.query(ClothingItem).filter(
            ClothingItem.user_id == current_user.id
        ).limit(5).all()

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

@router.get("/calendar/weekly", response_model=list[CalendarDayPreview])
def get_weekly_calendar_strip(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    API cho Screen 6 (Phần Top): Lấy chuỗi lịch 7 ngày trong tuần hiện tại.
    Trả về danh sách các ngày từ Thứ 2 đến Chủ Nhật kèm Outfit đã xếp lịch.
    """
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    
    days_mapping = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekly_schedule = []
    
    for i in range(7):
        current_date = start_of_week + datetime.timedelta(days=i)
        
        # Tìm xem ngày này trong DB User đã chọn mặc đồ chưa
        calendar_entry = db.query(UserCalendar).filter(
            UserCalendar.user_id == current_user.id,
            func.date(UserCalendar.date) == current_date
        ).first()
        
        outfit_data = None
        event_name = None
        notes = None
        
        # Nếu đã xếp lịch đồ mặc, map thông tin Outfit ra cho Mobile render
        if calendar_entry:
            event_name = calendar_entry.event_title
            notes = calendar_entry.notes
            if calendar_entry.outfit:
                outfit_data = build_outfit_recommendation_dict(calendar_entry.outfit)
            
        weekly_schedule.append({
            "id": calendar_entry.id if calendar_entry else None,
            "history_id": calendar_entry.id if calendar_entry else None,
            "date": current_date,
            "day_name": days_mapping[i],
            "is_highlighted": (current_date == today),
            "event_title": event_name,
            "notes": notes,
            "outfit": outfit_data
        })
        
    return weekly_schedule

@router.get("/insights", response_model=StyleInsightsResponse)
def get_wardrobe_style_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    API tính toán tỷ lệ sử dụng tủ đồ linh hoạt từ cơ sở dữ liệu.
    """
    pref_style = cast(List[str], current_user.preferred_style or ["Casual"])
    top_style = ", ".join(pref_style)

    total_items = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id).count()
    if total_items == 0:
        return {
            "utilization_rate": 0,
            "total_items": 0,
            "items_worn_this_month": 0,
            "top_style": top_style
        }
        
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    worn_items_count = db.query(func.count(func.distinct(outfit_item_association.c.clothing_item_id))).\
        select_from(UserCalendar).\
        join(OutfitCombo, UserCalendar.outfit_combo_id == OutfitCombo.id).\
        join(outfit_item_association, OutfitCombo.id == outfit_item_association.c.outfit_id).\
        filter(UserCalendar.user_id == current_user.id, UserCalendar.date >= thirty_days_ago).\
        scalar() or 0

    utilization_rate = int((worn_items_count / total_items) * 100)

    return {
        "utilization_rate": utilization_rate,
        "total_items": total_items,
        "items_worn_this_month": worn_items_count,
        "top_style": top_style
    }

@router.get("/calendar/insights", response_model=CalendarInsightsResponse)
async def get_calendar_insights(lat: float = 21.0285, lon: float = 105.8542, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    API Dự báo 3 ngày thực tế & Phân tích Đồ chưa mặc từ tủ đồ của người dùng.
    """
    total_items = db.query(ClothingItem).filter(ClothingItem.user_id == current_user.id).count()
    
    # 1. Lọc danh sách ID các món đồ đã từng lên lịch trong 60 ngày qua
    sixty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=60)
    worn_item_ids_query = db.query(outfit_item_association.c.clothing_item_id).\
        select_from(UserCalendar).\
        join(OutfitCombo, UserCalendar.outfit_combo_id == OutfitCombo.id).\
        join(outfit_item_association, OutfitCombo.id == outfit_item_association.c.outfit_id).\
        filter(UserCalendar.user_id == current_user.id, UserCalendar.date >= sixty_days_ago)

    # Đếm chính xác số đồ chưa hề được chọn mặc trong 60 ngày
    unworn_count = db.query(ClothingItem).filter(
        ClothingItem.user_id == current_user.id,
        ClothingItem.id.not_in(worn_item_ids_query)
    ).count()

    worn_count_60 = total_items - unworn_count
    utilization_rate = int((worn_count_60 / total_items) * 100) if total_items > 0 else 0

    # 2. Dự báo thời tiết 3 ngày thực tế từ WeatherAPI
    forecast = await weather.get_forecast_by_coords(lat, lon, days=3)

    impact_level = "High" if unworn_count > 2 else "Moderate"
    rec_summary = f"{unworn_count} trang phục chưa được phối." if unworn_count > 0 else "Tủ đồ đang được tối ưu rất tốt."

    return {
        "utilization_rate": utilization_rate,
        "unworn_items_insight": {
            "count": unworn_count,
            "threshold_days": 60,
            "message": f"{unworn_count} món đồ trong tủ chưa được mặc trong 60 ngày qua. Bạn muốn Bán hay Phối lại?"
        },
        "next_3_days_forecast": forecast,
        "weather_impact": {
            "level": impact_level,
            "recommendation_summary": rec_summary
        }
    }








@router.post("/sync-offline-history")
def sync_offline_history(actions: list[OfflineSyncRequest], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    API đặc thù cho Mobile: Nhận một loạt các hành động mặc đồ 
    được lưu tạm dưới máy user khi họ bị mất mạng (Offline Mode).
    """
    if not actions or len(actions) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Danh sách lịch sử đồng bộ không được để trống."
        )

    for action in actions:
        # Lấy dữ liệu lưu tạm từ Mobile đẩy lên và nhét vào Postgres
        new_history = UserCalendar(
            user_id=current_user.id,
            date=action.local_timestamp, # Lấy đúng thời gian lúc user bấm dưới máy họ
            event_title=action.event_title,
            outfit_combo_id=action.outfit_id
        )
        db.add(new_history)
    db.commit()
    return {"status": "synced", "total_processed": len(actions)}

@router.get("/calendar", response_model=list[CalendarDayPreview])
def get_calendar_by_range(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Truy vấn lịch mặc đồ theo khoảng thời gian tùy chọn (start_date, end_date dạng YYYY-MM-DD).
    Nếu không truyền, mặc định lấy 30 ngày gần nhất.
    """
    today = datetime.date.today()
    if start_date:
        try:
            s_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            s_date = today - datetime.timedelta(days=15)
    else:
        s_date = today - datetime.timedelta(days=15)

    if end_date:
        try:
            e_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            e_date = today + datetime.timedelta(days=15)
    else:
        e_date = today + datetime.timedelta(days=15)

    days_mapping = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    results = []

    curr = s_date
    while curr <= e_date:
        calendar_entry = db.query(UserCalendar).filter(
            UserCalendar.user_id == current_user.id,
            func.date(UserCalendar.date) == curr
        ).first()

        outfit_data = None
        event_name = None
        notes = None
        if calendar_entry:
            event_name = calendar_entry.event_title
            notes = calendar_entry.notes
            if calendar_entry.outfit:
                outfit_data = build_outfit_recommendation_dict(calendar_entry.outfit)

        results.append({
            "id": calendar_entry.id if calendar_entry else None,
            "history_id": calendar_entry.id if calendar_entry else None,
            "date": curr,
            "day_name": days_mapping[curr.weekday()],
            "is_highlighted": (curr == today),
            "event_title": event_name,
            "notes": notes,
            "outfit": outfit_data
        })
        curr += datetime.timedelta(days=1)

    return results

@router.get("/calendar/daily", response_model=closet_schema.DailyCalendarResponse)
async def get_daily_calendar_detail(
    date: str,
    lat: float = 21.0285,
    lon: float = 105.8542,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Lấy chi tiết lịch mặc đồ của một ngày cụ thể (YYYY-MM-DD): Thời tiết, Outfit & Sự kiện/Ghi chú.
    """
    try:
        target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Định dạng ngày không hợp lệ. Vui lòng dùng YYYY-MM-DD.")

    today = datetime.date.today()
    days_mapping = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # 1. Truy vấn lịch trong DB
    calendar_entry = db.query(UserCalendar).filter(
        UserCalendar.user_id == current_user.id,
        func.date(UserCalendar.date) == target_date
    ).first()

    outfit_data = None
    event_title = None
    notes = None

    if calendar_entry:
        event_title = calendar_entry.event_title
        notes = calendar_entry.notes
        if calendar_entry.outfit:
            outfit_data = build_outfit_recommendation_dict(calendar_entry.outfit)

    # 2. Lấy thông tin dự báo thời tiết ngày đó nếu là ngày gần đây
    weather_status = None
    weather_icon = "cloud-sun"
    try:
        diff_days = (target_date - today).days
        if 0 <= diff_days <= 3:
            forecasts = await weather.get_forecast_by_coords(lat, lon, days=diff_days + 1)
            for f in forecasts:
                if f.get("date") == date:
                    weather_status = f"{f.get('condition')}, {f.get('temp_c')}°C"
                    weather_icon = f.get("icon", "cloud-sun")
                    break
        elif target_date == today:
            w_data = await weather.get_weather_by_coords(lat, lon)
            weather_status = f"{w_data.get('condition')}, {w_data.get('temp')}°C"
            weather_icon = weather.normalize_weather_icon(w_data.get('condition') or "")
    except Exception:
        pass

    return {
        "id": calendar_entry.id if calendar_entry else None,
        "history_id": calendar_entry.id if calendar_entry else None,
        "date": target_date,
        "day_name": days_mapping[target_date.weekday()],
        "is_highlighted": (target_date == today),
        "event_title": event_title,
        "notes": notes,
        "weather_status": weather_status,
        "weather_icon": weather_icon,
        "outfit": outfit_data
    }

@router.delete("/calendar/{history_id}")
def delete_calendar_history(
    history_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa bản ghi lịch sử mặc đồ (Hủy wear today)"""
    entry = db.query(UserCalendar).filter(
        UserCalendar.id == history_id,
        UserCalendar.user_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi lịch sử này.")

    db.delete(entry)
    db.commit()
    return {"status": "success", "message": "Đã xóa bản ghi lịch sử mặc đồ thành công."}

@router.post("/outfit/{outfit_id}/swap", response_model=closet_schema.OutfitRecommendation)
def swap_outfit_item(
    outfit_id: int,
    swap_in: closet_schema.SwapOutfitItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lưu lựa chọn thay thế món đồ vào bộ Outfit gợi ý hoặc cá nhân"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ phối đồ này.")

    item_ids = [i.id for i in outfit.items]
    if swap_in.old_item_id not in item_ids:
        raise HTTPException(status_code=400, detail="Món đồ cũ không có trong bộ phối đồ này.")

    new_item = db.query(ClothingItem).filter(
        ClothingItem.id == swap_in.new_item_id,
        ClothingItem.user_id == current_user.id
    ).first()
    if not new_item:
        raise HTTPException(status_code=404, detail="Không tìm thấy món đồ mới thay thế.")

    # Thay thế món đồ cũ bằng món mới
    updated_items = [i for i in outfit.items if i.id != swap_in.old_item_id]
    if new_item not in updated_items:
        updated_items.append(new_item)

    outfit.items = updated_items
    db.commit()
    db.refresh(outfit)

    return build_outfit_recommendation_dict(outfit)

@router.post("/calendar/schedule")
def schedule_calendar_event(
    req: closet_schema.CalendarScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Đặt trước Lịch mặc đồ cho một ngày trong tương lai"""
    outfit = db.query(OutfitCombo).filter(
        OutfitCombo.id == req.outfit_id,
        OutfitCombo.user_id == current_user.id
    ).first()
    if not outfit:
        raise HTTPException(status_code=404, detail="Không tìm thấy bộ phối đồ được chọn.")

    calendar_entry = db.query(UserCalendar).filter(
        UserCalendar.user_id == current_user.id,
        func.date(UserCalendar.date) == req.date
    ).first()

    raw_event_title = req.event_title or req.event_name
    event_title = raw_event_title.strip() if raw_event_title and raw_event_title.strip() else (outfit.style_type or "Scheduled Match")
    notes = req.notes.strip() if req.notes and req.notes.strip() else None

    if calendar_entry:
        calendar_entry.outfit_combo_id = outfit.id
        calendar_entry.event_title = event_title
        if notes is not None:
            calendar_entry.notes = notes
    else:
        new_entry = UserCalendar(
            user_id=current_user.id,
            outfit_combo_id=outfit.id,
            date=datetime.datetime.combine(req.date, datetime.time.min),
            event_title=event_title,
            notes=notes
        )
        db.add(new_entry)

    db.commit()
    return {"status": "success", "message": f"Đã đặt lịch mặc đồ cho ngày {req.date} thành công!"}

@router.get("/calendar/events", response_model=list[CalendarDayPreview])
def get_upcoming_calendar_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy danh sách các sự kiện sắp tới để AI Stylist chủ động chuẩn bị outfit gợi ý"""
    today = datetime.date.today()
    entries = db.query(UserCalendar).filter(
        UserCalendar.user_id == current_user.id,
        func.date(UserCalendar.date) >= today
    ).order_by(UserCalendar.date.asc()).all()

    days_mapping = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    results = []

    for entry in entries:
        entry_date = entry.date.date() if isinstance(entry.date, datetime.datetime) else entry.date
        outfit_data = None
        if entry.outfit:
            outfit_data = build_outfit_recommendation_dict(entry.outfit)

        results.append({
            "id": entry.id,
            "history_id": entry.id,
            "date": entry_date,
            "day_name": days_mapping[entry_date.weekday()],
            "is_highlighted": (entry_date == today),
            "event_title": entry.event_title,
            "notes": entry.notes,
            "outfit": outfit_data
        })

    return results
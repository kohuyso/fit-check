# app/routers/dashboard.py
import datetime
import os
from typing import List, cast
from fastapi import APIRouter, Depends, HTTPException, status
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

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard & Recommendation"])

def get_or_create_outfit_combo(db: Session, user_id: int, style_type: str, item_ids: list[int]) -> OutfitCombo:
    """Helper để tìm hoặc tạo mới một OutfitCombo tránh bị trùng lặp bộ đồ giống nhau trong DB"""
    # 1. Tìm các combo hiện tại của user xem có combo nào chứa chính xác các item_ids này không
    combos = db.query(OutfitCombo).filter(OutfitCombo.user_id == user_id).all()
    for combo in combos:
        existing_ids = [item.id for item in combo.items]
        if sorted(existing_ids) == sorted(item_ids):
            return combo

    # 2. Tạo mới combo
    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(item_ids)
    ).all()
    
    new_combo = OutfitCombo(user_id=user_id, style_type=style_type, items=items)
    db.add(new_combo)
    db.commit()
    db.refresh(new_combo)
    return new_combo

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
    
    # 2. Định dạng lịch trình (Thực tế sẽ sync từ lịch công ty, ở đây mock theo UI yêu cầu)
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
                            recommendations.append({
                                "outfit_id": combo_db.id,
                                "style_type": combo_db.style_type,
                                "items": [
                                    {
                                        "id": cast(int, item.id),
                                        "name": f"{item.style_tag} {item.category}",
                                        "category": item.category,
                                        "image_url": item.image_url,
                                        "color_code": item.color_code,
                                        "style_tag": item.style_tag
                                    } for item in combo_db.items
                                ]
                            })
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
                
                recommendations.append({
                    "outfit_id": combo_db.id,
                    "style_type": combo_db.style_type,
                    "items": [
                        {
                            "id": cast(int, item.id),
                            "name": f"{item.style_tag} {item.category}",
                            "category": item.category,
                            "image_url": item.image_url,
                            "color_code": item.color_code,
                            "style_tag": item.style_tag
                        } for item in combo_db.items
                    ]
                })

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
    "footwear": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay"],
    "shoes": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay"],
    "shoe": ["Shoes", "shoes", "footwear", "Footwear", "Shoe", "giay"],
    "shirts": ["Shirts", "shirts", "shirt", "Shirt", "ao"],
    "shirt": ["Shirts", "shirts", "shirt", "Shirt", "ao"],
    "pants": ["Pants", "pants", "pant", "Pant", "quan"],
    "pant": ["Pants", "pants", "pant", "Pant", "quan"],
    "jackets": ["Jackets", "jackets", "jacket", "Jacket", "ao khoac"],
    "jacket": ["Jackets", "jackets", "jacket", "Jacket", "ao khoac"],
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
        
        # Nếu đã xếp lịch đồ mặc, map thông tin Outfit ra cho Mobile render
        if calendar_entry:
            event_name = calendar_entry.event_title
            if calendar_entry.outfit:
                outfit_data = {
                    "outfit_id": calendar_entry.outfit.id,
                    "style_type": calendar_entry.outfit.style_type or "Daily Set",
                    "items": [
                        {
                            "id": cast(int, item.id),
                            "name": f"{item.style_tag} {item.category}",
                            "category": item.category,
                            "image_url": item.image_url,
                            "color_code": item.color_code,
                            "style_tag": item.style_tag
                        } for item in calendar_entry.outfit.items
                    ]
                }
            
        weekly_schedule.append({
            "date": current_date,
            "day_name": days_mapping[i],
            "is_highlighted": (current_date == today),
            "event_title": event_name,
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
def get_calendar_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    API Dự báo 3 ngày & Phân tích Đồ chưa mặc thực tế từ tủ đồ của người dùng.
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

    # 2. Sinh lịch dự báo 3 ngày linh hoạt từ thời gian thực
    today = datetime.date.today()
    forecast = []
    conditions = [
        {"cond": "Cloudy", "icon": "cloud", "temp_offset": -2},
        {"cond": "Sunny", "icon": "sun", "temp_offset": 3},
        {"cond": "PartlyCloudy", "icon": "cloud-sun", "temp_offset": 1}
    ]
    base_temp = 24
    
    for i in range(1, 4):
        next_day = today + datetime.timedelta(days=i)
        c_info = conditions[(i - 1) % len(conditions)]
        offset_val: int = int(c_info["temp_offset"])
        forecast.append({
            "date": next_day.strftime("%Y-%m-%d"),
            "temp_c": base_temp + offset_val,
            "condition": str(c_info["cond"]),
            "icon": str(c_info["icon"])
        })

    impact_level = "High" if unworn_count > 2 else "Moderate"
    rec_summary = f"{unworn_count} items need restyling." if unworn_count > 0 else "Wardrobe fully active."

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
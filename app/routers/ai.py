# app/routers/ai.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Header
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional, cast

from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.closet import ClothingItem, OutfitCombo, ChatMessage
from app.schemas import closet_schema

from app.services import ai_engine
from app.services.outfit_service import get_or_create_outfit_combo, build_outfit_recommendation_dict



router = APIRouter(prefix="/api/v1/ai", tags=["AI Stylist"])


@router.get("/test-connection")
async def test_ai_connection():
    """
    API Kiểm tra trạng thái kết nối tới Gemini / OpenAI LLM.
    Trả về thông tin mô hình, API key mask, và thử nghiệm phản hồi trực tiếp.
    """
    api_key, api_url, text_model, vision_model = ai_engine.get_ai_config()
    
    if not api_key:
        return {
            "status": "error",
            "message": "Chưa cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY trong .env",
            "config": {"api_url": api_url, "model": text_model}
        }
        
    masked_key = f"{api_key[:6]}...{api_key[-4:]}"
    
    class MockItem:
        id = 1
        category = "Shirts"
        color_code = "#FFFFFF"
        style_tag = "Formal"
        
    try:
        outfits = await ai_engine.generate_outfits(1, "Nắng 28°C", "Đi họp", [MockItem()])
        if outfits:
            return {
                "status": "ok",
                "message": "Kết nối Gemini API thành công!",
                "config": {
                    "api_key_masked": masked_key,
                    "api_url": api_url,
                    "model": text_model
                },
                "sample_response": outfits
            }
        else:
            return {
                "status": "warning",
                "message": "Gọi API không thành công (API trả về rỗng hoặc gặp lỗi). Vui lòng kiểm tra log server.",
                "config": {
                    "api_key_masked": masked_key,
                    "api_url": api_url,
                    "model": text_model
                }
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ngoại lệ khi gọi API: {str(e)}",
            "config": {
                "api_key_masked": masked_key,
                "api_url": api_url,
                "model": text_model
            }
        }


@router.get("/style-suggestions", response_model=closet_schema.StyleSuggestionResponse)
async def get_style_suggestions(
    force_refresh: bool = False,
    tz: Optional[str] = None,
    x_timezone: Optional[str] = Header(None, alias="X-Timezone"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Gợi ý style (AI): Phân tích tủ đồ của người dùng và style yêu thích để đưa ra lời khuyên thời trang.
    Hỗ trợ truyền múi giờ qua header X-Timezone hoặc param tz (ví dụ: America/New_York, Asia/Ho_Chi_Minh).
    """
    user_id = cast(int, current_user.id)
    closet_items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    
    preferred_style = cast(List[str], current_user.preferred_style or ["Casual"])
    suggestions = await ai_engine.generate_style_suggestions(
        preferred_style, 
        closet_items, 
        force_refresh=force_refresh, 
        user_id=user_id,
        tz_name=x_timezone or tz
    )
    return suggestions



@router.post("/outfit-from-items", response_model=List[closet_schema.OutfitRecommendation])
async def get_outfit_from_items(
    req: closet_schema.OutfitFromItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Gợi ý outfit từ 1 hoặc vài món đồ (AI): Chọn trước các món đồ, AI sẽ phối thêm các đồ khác để hoàn thiện set đồ.
    """
    user_id = cast(int, current_user.id)
    
    if not req.item_ids or len(req.item_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất 1 món đồ từ tủ đồ của bạn."
        )

    # 1. Xác thực các món đồ được chọn có thuộc về user không
    selected_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ClothingItem.id.in_(req.item_ids)
    ).all()
    
    if not selected_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy các món đồ được chọn trong tủ đồ của bạn."
        )
        
    # 2. Sử dụng RAG Hybrid Search để tìm các món đồ tương thích nhất
    from app.services.embedding_service import search_wardrobe_hybrid
    selected_desc = ", ".join([f"{item.color_name or item.color_code} {item.category} ({item.style_tag})" for item in selected_items])
    rag_query = f"Complete outfit matching: {selected_desc}. Event: {req.event or 'Daily'}, Weather: {req.weather or 'Normal'}"

    other_items = await search_wardrobe_hybrid(
        db=db,
        user_id=user_id,
        query_text=rag_query,
        exclude_item_ids=req.item_ids,
        top_k=8
    )
    
    # 3. Gọi AI phối đồ với tập ứng viên Top-K đã được lọc qua RAG
    raw_combos = await ai_engine.generate_outfits_from_items(
        user_id=user_id,
        selected_items=selected_items,
        other_items=other_items,
        weather=req.weather or "Normal",
        event=req.event or "Daily Match"
    )
    
    recommendations = []
    for raw_combo in raw_combos:
        style_type = raw_combo.get("style_type", "AI Suggested Outfit")
        item_ids = raw_combo.get("items_ids", [])
        if item_ids:
            # Lưu vào DB để tạo OutfitCombo
            combo_db = get_or_create_outfit_combo(db, user_id, style_type, [int(x) for x in item_ids])
            if combo_db:
                recommendations.append(build_outfit_recommendation_dict(combo_db, weather_desc=req.weather))
                
    return recommendations


EVENT_LABEL_MAP = {
    "work": "Work & Business Formal/Smart Casual",
    "date": "Romantic Date Night & Dinner",
    "party": "Party & Evening Event",
    "gym": "Gym & Sports Workout",
    "casual": "Casual Daily Hangout"
}

@router.post("/outfit-by-event", response_model=closet_schema.OutfitRecommendation)
async def get_outfit_by_event(
    req: closet_schema.OutfitByEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Gợi ý Outfit theo sự kiện (AI RAG): Tìm kiếm ngữ nghĩa các món đồ phù hợp nhất với sự kiện và thời tiết.
    """
    user_id = cast(int, current_user.id)
    event_key = req.event_type.lower().strip() if req.event_type else "casual"
    event_label = EVENT_LABEL_MAP.get(event_key, req.event_type or "Daily Event")
    weather = req.weather_condition or "Normal"

    # Sử dụng RAG Hybrid Search lấy Top 10 món đồ phù hợp nhất cho sự kiện này
    from app.services.embedding_service import search_wardrobe_hybrid
    rag_query = f"Outfit for occasion: {event_label}, Weather: {weather}"
    closet_items = await search_wardrobe_hybrid(
        db=db,
        user_id=user_id,
        query_text=rag_query,
        top_k=10
    )

    if not closet_items or len(closet_items) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tủ đồ của bạn cần ít nhất 2 món đồ để AI có thể phối trang phục."
        )

    # Gọi AI engine sinh set phối đồ cho sự kiện này
    raw_combos = await ai_engine.generate_outfits(
        user_id=user_id,
        weather=weather,
        event=event_label,
        closet_items=closet_items
    )

    selected_combo = None
    if raw_combos and isinstance(raw_combos, list):
        for raw in raw_combos:
            style_type = raw.get("style_type", f"{event_key.capitalize()} Outfit")
            item_ids = raw.get("items_ids", [])
            if item_ids:
                selected_combo = get_or_create_outfit_combo(db, user_id, style_type, [int(x) for x in item_ids])
                if selected_combo:
                    break

    # Fallback nếu AI không khả dụng hoặc lỗi
    if not selected_combo:
        target_style = "Formal" if event_key in ("work", "party") else "Casual"
        matching_items = [i for i in closet_items if i.style_tag == target_style]
        source_items = matching_items if len(matching_items) >= 2 else closet_items

        shirts = [i for i in source_items if i.category.lower() in ("shirts", "shirt", "ao")]
        pants = [i for i in source_items if i.category.lower() in ("pants", "pant", "quan")]
        shoes = [i for i in source_items if i.category.lower() in ("shoes", "shoe", "giay")]

        combo_items = []
        if shirts:
            combo_items.append(shirts[0])
        if pants:
            combo_items.append(pants[0])
        if shoes:
            combo_items.append(shoes[0])

        if len(combo_items) < 2:
            for item in source_items:
                if item not in combo_items:
                    combo_items.append(item)
                    if len(combo_items) >= 2:
                        break

        item_ids = [cast(int, item.id) for item in combo_items if item.id is not None]
        selected_combo = get_or_create_outfit_combo(db, user_id, f"{event_key.capitalize()} Outfit", item_ids)

    return build_outfit_recommendation_dict(selected_combo, weather_desc=weather)


@router.post("/chat", response_model=closet_schema.AIChatResponse)
async def chat_and_modify_outfit(
    req: closet_schema.AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Yêu cầu hoặc sửa style/outfit bằng text giống phiên chat (AI).
    Nhận vào tin nhắn yêu cầu thay đổi trang phục hiện tại hoặc đề xuất set đồ mới.
    """
    if (not req.message or not req.message.strip()) and not req.image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập nội dung tin nhắn hoặc gửi hình ảnh trang phục."
        )
    user_id = cast(int, current_user.id)
    preferred_styles = cast(List[str], current_user.preferred_style or ["Casual"])
    preferred_style_str = ", ".join(preferred_styles)

    from app.services.fashion_agent import run_fashion_stylist_agent
    agent_result = await run_fashion_stylist_agent(
        user_id=user_id,
        message=req.message,
        db=db,
        user_location=req.weather or "Hanoi",
        preferred_style=preferred_style_str,
        history=req.history
    )

    reply = agent_result.get("reply", "Tôi đã xử lý yêu cầu của bạn.")
    suggested_outfit_id = agent_result.get("suggested_outfit_id")
    
    suggested_outfit_recommendation = None
    if suggested_outfit_id:
        combo_db = db.query(OutfitCombo).filter(
            OutfitCombo.id == suggested_outfit_id,
            OutfitCombo.user_id == user_id
        ).first()
        if combo_db:
            suggested_outfit_recommendation = build_outfit_recommendation_dict(combo_db, weather_desc=req.weather)
                
    recommended_outfit_card = None
    if suggested_outfit_recommendation and suggested_outfit_recommendation.get("items"):
        raw_items = suggested_outfit_recommendation["items"]
        if isinstance(raw_items, list):
            items_list: List[Dict[str, Any]] = cast(List[Dict[str, Any]], raw_items)
            items_summary = [{"id": item["id"], "name": str(item["name"])} for item in items_list]
            first_img = str(items_list[0]["image_url"]) if items_list else ""
            item_count = len(items_list)
            
            # Tổng hợp tag phong cách linh hoạt từ các món đồ trong outfit
            distinct_styles: List[str] = [
                str(item.get("style") or item.get("style_tag") or "Casual")
                for item in items_list
                if item.get("style") or item.get("style_tag")
            ]
            unique_styles = list(dict.fromkeys(distinct_styles))
            combined_style_tag = " • ".join(unique_styles) if unique_styles else "Smart Casual"
            if req.weather and "rain" in req.weather.lower():
                combined_style_tag += " • Waterproofed"
                
            recommended_outfit_card = {
                "outfit_id": suggested_outfit_recommendation["outfit_id"],
                "title": str(suggested_outfit_recommendation.get("style_type") or "AI Custom Look"),
                "style_tag": combined_style_tag,
                "image_url": first_img,
                "match_badge": "BEST MATCH" if item_count >= 3 else "STYLE MATCH",
                "weather_label": f"{req.weather or '22°C'}",
                "comfort_label": f"{item_count}-Piece Set",
                "items": items_summary
            }

    # 6. Lưu cuộc hội thoại vào CSDL
    try:
        user_msg_db = ChatMessage(
            user_id=user_id,
            role="user",
            content=req.message
        )
        db.add(user_msg_db)

        outfit_db_id = suggested_outfit_recommendation["outfit_id"] if suggested_outfit_recommendation else None
        ai_msg_db = ChatMessage(
            user_id=user_id,
            role="assistant",
            content=reply,
            suggested_outfit_id=outfit_db_id
        )
        db.add(ai_msg_db)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "reply": reply,
        "reply_text": reply,
        "suggested_outfit": suggested_outfit_recommendation,
        "recommended_outfit": recommended_outfit_card
    }


@router.get("/chat/history", response_model=List[closet_schema.ChatMessageResponse])
def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Lấy lịch sử hội thoại trò chuyện với AI Stylist"""
    messages = db.query(ChatMessage).filter(
        ChatMessage.user_id == current_user.id
    ).order_by(ChatMessage.created_at.asc()).all()
    return messages


@router.delete("/chat/history")
def clear_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Xóa toàn bộ lịch sử trò chuyện với AI Stylist"""
    db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).delete()
    db.commit()
    return {"status": "success", "message": "Đã xóa lịch sử trò chuyện AI thành công."}

@router.post("/chat/feedback")
def submit_chat_feedback(
    req: closet_schema.ChatMessageFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API Người dùng đánh giá phản hồi của AI Stylist (like/dislike & comment)"""
    if req.rating not in ("like", "dislike"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Đánh giá rating phải là 'like' hoặc 'dislike'."
        )

    msg = db.query(ChatMessage).filter(
        ChatMessage.id == req.message_id,
        ChatMessage.user_id == current_user.id
    ).first()

    if not msg:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn này trong lịch sử AI chat.")

    msg.rating = req.rating
    if req.comment is not None:
        msg.feedback_comment = req.comment.strip()

    db.commit()
    return {"status": "success", "message": "Cảm ơn bạn đã gửi đánh giá phản hồi cho AI Stylist!"}




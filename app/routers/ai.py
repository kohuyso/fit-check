# app/routers/ai.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, cast

from app.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.closet import ClothingItem, OutfitCombo
from app.schemas import closet_schema
from app.services import ai_engine
from app.routers.dashboard import get_or_create_outfit_combo

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    API Gợi ý style (AI): Phân tích tủ đồ của người dùng và style yêu thích để đưa ra lời khuyên thời trang.
    """
    user_id = cast(int, current_user.id)
    closet_items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    
    preferred_style = cast(List[str], current_user.preferred_style or ["Casual"])
    suggestions = await ai_engine.generate_style_suggestions(preferred_style, closet_items)
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
        
    # 2. Lấy tất cả các món đồ còn lại của user
    other_items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user_id,
        ~ClothingItem.id.in_(req.item_ids)
    ).all()
    
    # 3. Gọi AI phối đồ
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
                
    return recommendations


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
    
    # 1. Lấy toàn bộ tủ đồ của user
    closet_items = db.query(ClothingItem).filter(ClothingItem.user_id == user_id).all()
    
    # 2. Lấy thông tin outfit hiện tại nếu có
    current_outfit_items = []
    if req.current_outfit_id:
        outfit = db.query(OutfitCombo).filter(
            OutfitCombo.id == req.current_outfit_id,
            OutfitCombo.user_id == user_id
        ).first()
        if outfit:
            current_outfit_items = cast(list, outfit.items)
            
    # 3. Format history từ Pydantic sang dict cho service AI
    history_list = []
    if req.history:
        for h in req.history:
            msg_dict = {"role": h.role, "content": h.content}
            if h.image_url:
                msg_dict["image_url"] = h.image_url
            history_list.append(msg_dict)
        
    # 4. Gọi AI xử lý tin nhắn chat và chỉnh sửa phối đồ
    result = await ai_engine.chat_modify_outfit(
        user_id=user_id,
        message=req.message,
        image_url=req.image_url,
        history=history_list,
        current_outfit_items=current_outfit_items,
        closet_items=closet_items,
        weather=req.weather or "Normal",
        event=req.event or "Daily Match"
    )
    
    reply = result.get("reply", "Tôi đã xử lý yêu cầu của bạn.")
    suggested_outfit_data = result.get("suggested_outfit")
    
    suggested_outfit_recommendation = None
    
    # 5. Nếu AI trả về set đồ được gợi ý/chỉnh sửa mới
    if suggested_outfit_data:
        style_type = suggested_outfit_data.get("style_type", "AI Modified Outfit")
        item_ids = suggested_outfit_data.get("items_ids", [])
        if item_ids:
            combo_db = get_or_create_outfit_combo(db, user_id, style_type, [int(x) for x in item_ids])
            if combo_db:
                suggested_outfit_recommendation = {
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
                }
                
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


    return {
        "reply": reply,
        "reply_text": reply,
        "suggested_outfit": suggested_outfit_recommendation,
        "recommended_outfit": recommended_outfit_card
    }



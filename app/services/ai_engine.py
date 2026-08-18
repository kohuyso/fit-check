import hashlib
import json
import datetime
import httpx
from zoneinfo import ZoneInfo
from typing import Any, List, Optional, Union, Dict, Tuple

from app.core.config import settings
from app.core.logger import logger
from app.database import redis_client

def get_user_local_date(tz_name: Optional[str] = None) -> str:
    """
    Lấy ngày hiện tại theo múi giờ local của User (ví dụ: 'Asia/Ho_Chi_Minh', 'America/New_York', 'Europe/London').
    Nếu tz_name không hợp lệ hoặc rỗng, mặc định fallback về 'Asia/Ho_Chi_Minh'.
    """
    if tz_name and tz_name.strip():
        try:
            return datetime.datetime.now(ZoneInfo(tz_name.strip())).strftime("%Y-%m-%d")
        except Exception:
            pass
    try:
        return datetime.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.date.today().isoformat()

def _compute_closet_signature(closet_items: List[Any]) -> str:
    """Tạo chữ ký SHA-256 từ danh sách món đồ trong tủ đồ để làm cache key."""
    simplified = sorted([
        f"{getattr(item, 'id', 0)}:{getattr(item, 'category', '')}:{getattr(item, 'color_code', '')}:{getattr(item, 'style_tag', '')}"
        for item in closet_items
    ])
    raw_str = "|".join(simplified)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]


def get_ai_config() -> Tuple[Optional[str], str, str, str]:
    """
    Trả về (api_key, api_url, text_model, vision_model).
    Tự động ưu tiên GEMINI_API_KEY, fallback sang OPENAI_API_KEY.
    """
    gemini_key = settings.GEMINI_API_KEY
    openai_key = settings.OPENAI_API_KEY

    if gemini_key and "your_" not in gemini_key and gemini_key.strip():
        model = settings.GEMINI_MODEL
        return (
            gemini_key.strip(),
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            model,
            model,
        )

    if openai_key and "your_" not in openai_key and openai_key.strip():
        key = openai_key.strip()
        if key.startswith("AIza"):
            model = settings.GEMINI_MODEL
            return (
                key,
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                model,
                model,
            )
        return (
            key,
            "https://api.openai.com/v1/chat/completions",
            "gpt-4o-mini",
            "gpt-4o-mini",
        )

    logger.warning("No valid AI API Key (GEMINI_API_KEY / OPENAI_API_KEY) found. Fallback local logic will be used.")
    return (None, "", "", "")


async def generate_outfits(
    user_id: int, 
    weather: str, 
    event: str, 
    closet_items: List[Any],
    force_refresh: bool = False,
    tz_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    AI ĐÍCH THỰC: Đưa toàn bộ tủ đồ và bối cảnh vào LLM để suy luận ra bộ phối tối ưu.
    Có áp dụng Redis Cache (TTL 1 giờ) để tối ưu chi phí và tốc độ gọi Gemini API.
    """
    today_str = get_user_local_date(tz_name)
    closet_sig = _compute_closet_signature(closet_items)
    weather_clean = weather.strip().lower()
    event_clean = event.strip().lower()
    cache_key_hash = hashlib.sha256(f"{today_str}:{weather_clean}:{event_clean}:{closet_sig}".encode("utf-8")).hexdigest()[:16]
    cache_key = f"ai_cache:outfits:{user_id}:{today_str}:{cache_key_hash}"

    if not force_refresh:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"[Redis Cache HIT] generate_outfits user_id={user_id}")
                return json.loads(cached_data)
        except Exception as cache_err:
            logger.warning(f"[Redis Cache Error] generate_outfits get failed: {cache_err}")

    closet_description = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in closet_items
    ]

    prompt = f"""
    You are a premium AI Fashion Stylist for busy professionals.
    Context today:
    - Weather: {weather}
    - User's Schedule: {event}
    
    Available Wardrobe:
    {json.dumps(closet_description)}
    
    Task: Create exactly 3 distinct outfit combinations (each combo must include 1 upper body item, 1 lower body item, and 1 footwear item).
    The combinations MUST make sense for the weather and event.
    
    Return ONLY a strict JSON object with an "outfits" key containing the list of combinations:
    {{
      "outfits": [
        {{"style_type": "Executive Meeting Set", "items_ids": [1, 5, 12]}},
        {{"style_type": "Comfortable Professional", "items_ids": [2, 5, 14]}},
        {{"style_type": "Rain-Ready Formal", "items_ids": [3, 8, 15]}}
      ]
    }}
    """

    api_key, api_url, text_model, _ = get_ai_config()
    if api_key:
        try:
            timeout_cfg = httpx.Timeout(settings.AI_REQUEST_TIMEOUT, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": text_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "response_format": { "type": "json_object" }
                    }
                )
                
                if response.status_code == 200:
                    ai_res = response.json()
                    raw_json = ai_res["choices"][0]["message"]["content"]
                    parsed_data = json.loads(raw_json)
                    
                    outfits = []
                    if isinstance(parsed_data, dict):
                        outfits = parsed_data.get("outfits", [])
                    elif isinstance(parsed_data, list):
                        outfits = parsed_data
                        
                    if outfits:
                        try:
                            redis_client.setex(cache_key, 3600, json.dumps(outfits, ensure_ascii=False))
                        except Exception as cache_err:
                            logger.warning(f"[Redis Cache Error] generate_outfits setex failed: {cache_err}")
                        return outfits
                elif response.status_code == 429:
                    logger.warning(f"generate_outfits AI API Rate Limit / Quota Exceeded [429]: {response.text}")
                else:
                    logger.error(f"generate_outfits API Error [{response.status_code}]: {response.text}")
        except httpx.TimeoutException as te:
            logger.warning(f"generate_outfits AI API Timeout ({settings.AI_REQUEST_TIMEOUT}s): {te}. Using local fallback logic.")
        except Exception as e:
            logger.exception(f"generate_outfits exception: {e}")
            
    # Fallback local logic if AI API is unavailable, times out, rate-limited, or errors
    if not closet_items:
        return []

    shirts = [i for i in closet_items if i.category.lower() in ("shirts", "shirt")]
    pants = [i for i in closet_items if i.category.lower() in ("pants", "pant")]
    shoes = [i for i in closet_items if i.category.lower() in ("shoes", "shoe")]
    jackets = [i for i in closet_items if i.category.lower() in ("jackets", "jacket")]

    outfits = []
    style_names = ["Executive Meeting Set", "Comfortable Professional", "Rain-Ready Formal"]
    num_combos = min(3, max(1, len(closet_items)))

    for i in range(num_combos):
        combo_ids = []
        if shirts:
            combo_ids.append(shirts[i % len(shirts)].id)
        if pants:
            combo_ids.append(pants[i % len(pants)].id)
        if shoes:
            combo_ids.append(shoes[i % len(shoes)].id)
        if jackets and i == 0:
            combo_ids.append(jackets[0].id)

        if len(combo_ids) < 2:
            for item in closet_items:
                if item.id not in combo_ids:
                    combo_ids.append(item.id)
                    if len(combo_ids) >= 2:
                        break

        if combo_ids:
            outfits.append({
                "style_type": style_names[i % len(style_names)],
                "items_ids": combo_ids
            })

    return outfits


async def generate_style_suggestions(
    preferred_style: Union[str, List[str]], 
    closet_items: List[Any],
    force_refresh: bool = False,
    user_id: Optional[int] = None,
    tz_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    AI Style Suggestion: Phân tích tủ đồ của người dùng và preferred style để gợi ý.
    Có áp dụng Redis Cache tự động refresh khi sang ngày mới (theo local time của user) và theo từng user.
    """
    if isinstance(preferred_style, str):
        style_list = [preferred_style]
    else:
        style_list = preferred_style

    style_str = ", ".join(style_list)
    today_str = get_user_local_date(tz_name)
    closet_sig = _compute_closet_signature(closet_items)
    
    uid_str = f"u{user_id}" if user_id is not None else (f"u{closet_items[0].user_id}" if closet_items and hasattr(closet_items[0], "user_id") else "anon")
    cache_key_hash = hashlib.sha256(f"{today_str}:{style_str.lower()}:{closet_sig}".encode("utf-8")).hexdigest()[:16]
    cache_key = f"ai_cache:style:{uid_str}:{today_str}:{cache_key_hash}"

    if not force_refresh:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"[Redis Cache HIT] generate_style_suggestions user={uid_str} date={today_str}")
                return json.loads(cached_data)
        except Exception as cache_err:
            logger.warning(f"[Redis Cache Error] generate_style_suggestions get failed: {cache_err}")

    closet_description = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in closet_items
    ]

    prompt = f"""
    You are a premium AI Fashion Stylist.
    Analyze the user's wardrobe and preferred style to provide personalized style suggestions.

    User's Preferred Style: {style_str}

    Wardrobe Items:
    {json.dumps(closet_description, ensure_ascii=False)}

    Task:
    1. Analyze the dominant styles, categories, and colors in the user's wardrobe.
    2. Provide a detailed fashion profile analysis based on their wardrobe and preferred style (in Vietnamese).
    3. Provide 3 action-oriented styling tips (in Vietnamese).
    4. Recommend 2 complete look templates that can be built using their wardrobe or close equivalents.
    5. Suggest 2 items they should consider adding to their wardrobe to enhance their style options.

    Return ONLY a strict JSON object structure:
    {{
      "preferred_style": {json.dumps(style_list)},
      "style_analysis": "Phân tích chi tiết...",
      "style_tips": ["Mẹo 1", "Mẹo 2", "Mẹo 3"],
      "recommended_looks": [
        {{"name": "Tên Look 1", "description": "Mô tả phối...", "occasion": "Dịp 1"}},
        {{"name": "Tên Look 2", "description": "Mô tả phối...", "occasion": "Dịp 2"}}
      ],
      "suggested_additions": ["Món gợi ý mua thêm 1", "Món gợi ý mua thêm 2"]
    }}
    """

    api_key, api_url, text_model, _ = get_ai_config()
    if api_key:
        try:
            timeout_cfg = httpx.Timeout(settings.AI_REQUEST_TIMEOUT, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": text_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                        "response_format": { "type": "json_object" }
                    }
                )
                if response.status_code == 200:
                    ai_res = response.json()
                    raw_json = ai_res["choices"][0]["message"]["content"]
                    parsed_data = json.loads(raw_json)
                    parsed_data["preferred_style"] = style_list
                    try:
                        redis_client.setex(cache_key, 14400, json.dumps(parsed_data, ensure_ascii=False))
                    except Exception as cache_err:
                        logger.warning(f"[Redis Cache Error] generate_style_suggestions setex failed: {cache_err}")
                    return parsed_data
                elif response.status_code == 429:
                    logger.warning(f"generate_style_suggestions AI API Rate Limit / Quota Exceeded [429]: {response.text}")
                else:
                    logger.error(f"generate_style_suggestions API Error [{response.status_code}]: {response.text}")
        except httpx.TimeoutException as te:
            logger.warning(f"generate_style_suggestions AI API Timeout ({settings.AI_REQUEST_TIMEOUT}s): {te}. Using local fallback logic.")
        except Exception as e:
            logger.exception(f"generate_style_suggestions exception: {e}")

    # Fallback local logic
    analysis = "Gu thời trang hiện tại của bạn: "
    if len(closet_items) > 0:
        analysis += "Phong cách chủ đạo của bạn nghiêng về sự lịch lãm, công sở (Formal), rất phù hợp cho công việc.*"
    else:
        analysis += "Bạn yêu thích sự thoải mái, năng động khi tủ đồ có nhiều quần áo phong cách thường ngày (Casual).*"

    fallback_res = {
        "preferred_style": [f"{s}*" for s in style_list],
        "style_analysis": analysis,
        "style_tips": [
            "Hãy thử phối quần Âu (Formal) với một chiếc áo phông đơn giản để tạo phong cách Smart Casual độc đáo.*",
            "Tập trung vào sự tương phản màu sắc giữa phần trên và phần dưới (ví dụ áo sáng màu phối cùng quần tối màu).*",
            "Nếu thời tiết trở lạnh hoặc mưa, hãy khoác thêm một chiếc Jacket tối màu để tăng điểm nhấn.*"
        ],
        "recommended_looks": [
            {
                "name": "Năng động cuối tuần*",
                "description": "Phối áo thun basic cùng quần pants co giãn và đôi giày thể thao yêu thích của bạn.*",
                "occasion": "Đi chơi, gặp gỡ bạn bè*"
            },
            {
                "name": "Thanh lịch công sở*",
                "description": "Kết hợp áo sơ mi phom đứng cùng quần tối màu và giày tây hoặc giày da trơn.*",
                "occasion": "Họp hành, làm việc văn phòng*"
            }
        ],
        "suggested_additions": [
            "Một chiếc áo khoác Blazer màu trung tính để dễ dàng khoác ngoài mọi set đồ.*",
            "Đôi giày Sneaker trắng tối giản để nâng tầm phong cách casual.*"
        ]
    }

    try:
        redis_client.setex(cache_key, 14400, json.dumps(fallback_res, ensure_ascii=False))
    except Exception as cache_err:
        logger.warning(f"[Redis Cache Error] generate_style_suggestions fallback setex failed: {cache_err}")

    return fallback_res


async def generate_outfits_from_items(
    user_id: int, 
    selected_items: List[Any], 
    other_items: List[Any], 
    weather: str, 
    event: str,
    force_refresh: bool = False,
    tz_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    AI Suggestion from selected items: Phối đồ bắt buộc phải chứa các món đồ người dùng chọn.
    Có áp dụng Redis Cache (TTL 1 giờ) để tối ưu chi phí và tốc độ gọi Gemini API.
    """
    today_str = get_user_local_date(tz_name)
    selected_ids = sorted([item.id for item in selected_items])
    other_sig = _compute_closet_signature(other_items)
    weather_clean = weather.strip().lower()
    event_clean = event.strip().lower()
    cache_key_hash = hashlib.sha256(f"{today_str}:{selected_ids}:{weather_clean}:{event_clean}:{other_sig}".encode("utf-8")).hexdigest()[:16]
    cache_key = f"ai_cache:outfits_from_items:{user_id}:{today_str}:{cache_key_hash}"

    if not force_refresh:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"[Redis Cache HIT] generate_outfits_from_items user_id={user_id}")
                return json.loads(cached_data)
        except Exception as cache_err:
            logger.warning(f"[Redis Cache Error] generate_outfits_from_items get failed: {cache_err}")

    selected_items_desc = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in selected_items
    ]
    other_items_desc = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in other_items
    ]

    prompt = f"""
    You are a premium AI Fashion Stylist.
    The user wants to build an outfit starting with these specific items:
    {json.dumps(selected_items_desc, ensure_ascii=False)}

    Here is the rest of their available wardrobe:
    {json.dumps(other_items_desc, ensure_ascii=False)}

    Context:
    - Weather: {weather}
    - Event: {event}

    Task: Create exactly 3 distinct outfit combinations.
    CRITICAL: Every combination MUST include ALL of the starting items ({selected_ids}), and complete the set by adding appropriate items from the rest of the wardrobe.
    
    Return ONLY a strict JSON object with an "outfits" key containing the list of combinations:
    {{
      "outfits": [
        {{"style_type": "Smart Casual Combination", "items_ids": [1, 5, 12]}},
        {{"style_type": "Cozy Autumn Set", "items_ids": [1, 6, 14]}},
        {{"style_type": "Refined Classic Look", "items_ids": [1, 8, 15]}}
      ]
    }}
    """

    api_key, api_url, text_model, _ = get_ai_config()
    if api_key:
        try:
            timeout_cfg = httpx.Timeout(settings.AI_REQUEST_TIMEOUT, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": text_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.4,
                        "response_format": { "type": "json_object" }
                    }
                )
                if response.status_code == 200:
                    ai_res = response.json()
                    raw_json = ai_res["choices"][0]["message"]["content"]
                    parsed_data = json.loads(raw_json)
                    res_outfits = []
                    if isinstance(parsed_data, dict):
                        res_outfits = parsed_data.get("outfits", [])
                    elif isinstance(parsed_data, list):
                        res_outfits = parsed_data

                    if res_outfits:
                        try:
                            redis_client.setex(cache_key, 3600, json.dumps(res_outfits, ensure_ascii=False))
                        except Exception as cache_err:
                            logger.warning(f"[Redis Cache Error] generate_outfits_from_items setex failed: {cache_err}")
                        return res_outfits
                elif response.status_code == 429:
                    logger.warning(f"generate_outfits_from_items AI API Rate Limit / Quota Exceeded [429]: {response.text}")
                else:
                    logger.error(f"generate_outfits_from_items API Error [{response.status_code}]: {response.text}")
        except httpx.TimeoutException as te:
            logger.warning(f"generate_outfits_from_items AI API Timeout ({settings.AI_REQUEST_TIMEOUT}s): {te}. Using local fallback logic.")
        except Exception as e:
            logger.exception(f"generate_outfits_from_items exception: {e}")

    # Fallback local logic
    outfits = []
    other_cats: Dict[str, List[Any]] = {}
    for item in other_items:
        other_cats.setdefault(item.category.lower(), []).append(item)
        
    selected_cats = {item.category.lower() for item in selected_items}
    
    for i in range(3):
        combo_ids = list(selected_ids)
        for cat in ["shirts", "pants", "shoes"]:
            if cat not in selected_cats and cat in other_cats:
                cat_list = other_cats[cat]
                item_to_add = cat_list[i % len(cat_list)]
                if item_to_add.id not in combo_ids:
                    combo_ids.append(item_to_add.id)
                    
        if len(combo_ids) < 2:
            for item in other_items:
                if item.id not in combo_ids:
                    combo_ids.append(item.id)
                    if len(combo_ids) >= 2:
                        break
                        
        outfits.append({
            "style_type": f"Bộ phối gợi ý {i+1} (Từ đồ chọn)",
            "items_ids": combo_ids
        })
        
    return outfits


async def chat_modify_outfit(
    user_id: int,
    message: str,
    history: List[Dict[str, Any]],
    current_outfit_items: List[Any],
    closet_items: List[Any],
    weather: str,
    event: str,
    image_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    AI Chat Modifier: Cho phép sửa hoặc yêu cầu style/outfit bằng text và hình ảnh.
    """
    closet_description = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in closet_items
    ]
    current_outfit_desc = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in current_outfit_items
    ]

    system_prompt = f"""You are a premium AI Fashion Stylist.
The user is asking to request or modify their outfit or style.

Current Outfit (if any):
{json.dumps(current_outfit_desc, ensure_ascii=False)}

User's Available Wardrobe:
{json.dumps(closet_description, ensure_ascii=False)}

Context:
- Weather: {weather}
- Event: {event}

Task:
1. Analyze the user's message and any uploaded images.
2. Determine if they want to modify the current outfit, suggest a new outfit, or just chat about style.
3. Select items from their available wardrobe that match their request.
4. Provide a friendly response in Vietnamese explaining the changes you made.

Return ONLY a strict JSON object:
{{
  "reply": "Lời phản hồi bằng tiếng Việt...",
  "suggested_outfit": {{
    "style_type": "Tên phong cách",
    "items_ids": [1, 5, 12]
  }}
}}
If no outfit change is needed, set "suggested_outfit" to null.
"""

    openai_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    for msg in history:
        role = msg.get("role", "user")
        content_text = msg.get("content", "")
        msg_img = msg.get("image_url")
        
        if msg_img:
            openai_messages.append({
                "role": role,
                "content": [
                    {"type": "text", "text": content_text},
                    {"type": "image_url", "image_url": {"url": msg_img}}
                ]
            })
        else:
            openai_messages.append({
                "role": role,
                "content": content_text
            })

    if image_url:
        openai_messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": message},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        })
    else:
        openai_messages.append({
            "role": "user",
            "content": message
        })

    api_key, api_url, text_model, vision_model = get_ai_config()
    if api_key:
        model_to_use = vision_model if image_url else text_model
        try:
            timeout_cfg = httpx.Timeout(settings.AI_REQUEST_TIMEOUT + 5.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_to_use,
                        "messages": openai_messages,
                        "temperature": 0.5,
                        "response_format": { "type": "json_object" }
                    }
                )
                if response.status_code == 200:
                    ai_res = response.json()
                    raw_json = ai_res["choices"][0]["message"]["content"]
                    parsed_data = json.loads(raw_json)
                    return parsed_data
                elif response.status_code == 429:
                    logger.warning(f"chat_modify_outfit AI API Rate Limit / Quota Exceeded [429]: {response.text}")
                else:
                    logger.error(f"chat_modify_outfit API Error [{response.status_code}]: {response.text}")
        except httpx.TimeoutException as te:
            logger.warning(f"chat_modify_outfit AI API Timeout: {te}. Using local fallback logic.")
        except Exception as e:
            logger.exception(f"chat_modify_outfit exception: {e}")

    # Fallback local logic
    msg_lower = message.lower()
    reply = "Tôi đã ghi nhận yêu cầu của bạn. "
    new_items_ids = [item.id for item in current_outfit_items]
    
    jackets = [i for i in closet_items if i.category.lower() in ("jackets", "jacket")]
    formal_pants = [i for i in closet_items if i.category.lower() in ("pants", "pant") and i.style_tag == "Formal"]
    casual_pants = [i for i in closet_items if i.category.lower() in ("pants", "pant") and i.style_tag == "Casual"]
    shoes = [i for i in closet_items if i.category.lower() in ("shoes", "shoe")]
    
    modified = False
    style_type = "AI Modified Outfit"

    if any(k in msg_lower for k in ["ấm", "lạnh", "khoác", "jacket", "coat"]):
        has_jacket = any(item.category.lower() in ("jackets", "jacket") for item in current_outfit_items)
        if not has_jacket and jackets:
            new_items_ids.append(jackets[0].id)
            reply += "Tôi đã thêm một chiếc áo khoác ấm từ tủ đồ của bạn để phù hợp với thời tiết lạnh hơn. "
            style_type = "Cozy Layered Style"
            modified = True
        elif has_jacket:
            reply += "Bộ đồ hiện tại của bạn đã có áo khoác rồi nhé. "
        else:
            reply += "Rất tiếc tủ đồ của bạn chưa có chiếc áo khoác nào để thêm vào. "

    if any(k in msg_lower for k in ["lịch sự", "formal", "đi tiệc", "công sở", "họp"]):
        pants_in_outfit = [item for item in current_outfit_items if item.category.lower() in ("pants", "pant")]
        if pants_in_outfit and formal_pants:
            new_items_ids = [i for i in new_items_ids if i not in [p.id for p in pants_in_outfit]]
            new_items_ids.append(formal_pants[0].id)
            reply += "Tôi đã thay chiếc quần thường ngày bằng quần âu lịch sự hơn để phù hợp với môi trường công sở. "
            style_type = "Formal Corporate Style"
            modified = True
            
        shirts_in_outfit = [item for item in current_outfit_items if item.category.lower() in ("shirts", "shirt")]
        formal_shirts = [i for i in closet_items if i.category.lower() in ("shirts", "shirt") and i.style_tag == "Formal"]
        if shirts_in_outfit and formal_shirts:
            new_items_ids = [i for i in new_items_ids if i not in [s.id for s in shirts_in_outfit]]
            new_items_ids.append(formal_shirts[0].id)
            reply += "Tôi cũng nâng cấp áo của bạn thành áo sơ mi lịch lãm. "
            modified = True

    if any(k in msg_lower for k in ["thoải mái", "casual", "đi chơi", "dạo phố"]):
        pants_in_outfit = [item for item in current_outfit_items if item.category.lower() in ("pants", "pant")]
        if pants_in_outfit and casual_pants:
            new_items_ids = [i for i in new_items_ids if i not in [p.id for p in pants_in_outfit]]
            new_items_ids.append(casual_pants[0].id)
            reply += "Tôi đã đổi sang chiếc quần thoải mái hơn để bạn tiện đi dạo phố hay hẹn hò. "
            style_type = "Relaxed Casual Style"
            modified = True

    if any(k in msg_lower for k in ["giày", "shoe"]):
        shoes_in_outfit = [item for item in current_outfit_items if item.category.lower() in ("shoes", "shoe")]
        if shoes_in_outfit and len(shoes) > 1:
            other_shoes = [s for s in shoes if s.id not in [x.id for x in shoes_in_outfit]]
            if other_shoes:
                new_items_ids = [i for i in new_items_ids if i not in [s.id for s in shoes_in_outfit]]
                new_items_ids.append(other_shoes[0].id)
                reply += "Tôi đã đổi sang một đôi giày khác có sẵn trong tủ đồ để tạo cảm giác mới lạ. "
                modified = True
        elif not shoes_in_outfit and shoes:
            new_items_ids.append(shoes[0].id)
            reply += "Tôi đã thêm một đôi giày từ tủ đồ để hoàn thiện set đồ. "
            modified = True

    if not modified:
        if not current_outfit_items:
            default_items = closet_items[:3]
            new_items_ids = [item.id for item in default_items]
            if new_items_ids:
                reply = "Chào bạn! Tôi đã chọn phối cho bạn một set đồ cơ bản từ tủ đồ. Hãy cho tôi biết nếu bạn muốn điều chỉnh gì nhé!"
                suggested = {
                    "style_type": "Daily Classic Set",
                    "items_ids": new_items_ids
                }
            else:
                reply = "Chào bạn! Hiện tại tủ đồ của bạn đang trống, hãy chụp và quét thêm vài món đồ để tôi bắt đầu tư vấn nhé."
                suggested = None
        else:
            reply = "Chào bạn! Tôi có thể giúp bạn điều chỉnh bộ trang phục hiện tại (như đổi quần lịch sự hơn, thêm áo khoác, thay giày...). Bạn muốn thay đổi thế nào?"
            suggested = None
    else:
        suggested = {
            "style_type": style_type,
            "items_ids": new_items_ids
        }

    return {
        "reply": reply,
        "suggested_outfit": suggested
    }
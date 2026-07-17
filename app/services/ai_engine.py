import os
import json
import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def generate_outfits(user_id: int, weather: str, event: str, closet_items: list) -> list:
    """
    AI ĐÍCH THỰC: Đưa toàn bộ tủ đồ và bối cảnh vào LLM để suy luận ra bộ phối tối ưu.
    """
    # 1. Chuyển đổi danh sách tủ đồ của user thành dạng text để AI đọc hiểu
    closet_description = [
        {
            "item_id": item.id,
            "category": item.category,
            "color": item.color_code,
            "style": item.style_tag
        } for item in closet_items
    ]

    # 2. Xây dựng Prompt ra lệnh cho AI đóng vai trò Stylist cá nhân cao cấp
    prompt = f"""
    You are a premium AI Fashion Stylist for busy professionals.
    Context today:
    - Weather: {weather}
    - User's Schedule: {event}
    
    Available Wardrobe:
    {json.dumps(closet_description)}
    
    Task: Create exactly 3 distinct outfit combinations (each combo must include 1 upper body item, 1 lower body item, and 1 footwear item).
    The combinations MUST make sense for the weather (e.g., if rain, prefer formal shoes/boots over canvas) and the event (e.g., meeting requires Formal/Smart Casual).
    
    Return ONLY a strict JSON object with an "outfits" key containing the list of combinations, no conversational text:
    {{
      "outfits": [
        {{"style_type": "Executive Meeting Set", "items_ids": [1, 5, 12]}},
        {{"style_type": "Comfortable Professional", "items_ids": [2, 5, 14]}},
        {{"style_type": "Rain-Ready Formal", "items_ids": [3, 8, 15]}}
      ]
    }}
    """

    # 3. Gọi lên OpenAI API (hoặc các mô hình Open Source tự host như Llama 3)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini", # Dùng bản mini để tốc độ phản hồi siêu nhanh (~1 giây)
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3, # Để tính nhất quán cao, ít bị 'bịa' đồ
                "response_format": { "type": "json_object" } # Ép AI trả về JSON chuẩn
            },
            timeout=10.0
        )
        
        if response.status_code == 200:
            ai_res = response.json()
            raw_json = ai_res["choices"][0]["message"]["content"]
            parsed_data = json.loads(raw_json)
            
            # OpenAI JSON mode trả về Object ở gốc, lấy danh sách set đồ ra
            if isinstance(parsed_data, dict):
                return parsed_data.get("outfits", [])
            return parsed_data
            
    return [] # Fallback nếu API lỗi
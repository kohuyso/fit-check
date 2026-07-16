# app/services/weather.py
import os
import json
import httpx
from app.database import redis_client

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

async def get_weather_by_coords(lat: float, lon: float) -> dict:
    # Gom nhóm tọa độ theo bán kính nhỏ (làm tròn 2 chữ số thập phân) để tăng tỷ lệ trúng cache
    cache_key = f"weather:{round(lat, 2)}:{round(lon, 2)}"
    
    # 1. Kiểm tra bộ nhớ đệm Redis
    cached_data = redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    
    # 2. Nếu Cache Miss, gọi API ngoài (Ví dụ dùng OpenWeatherMap hoặc WeatherAPI)
    # Đoạn này viết giả lập cấu trúc chuẩn, bạn chỉ cần thay URL thật khi có API Key
    url = f"https://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={lat},{lon}&lang=vi"
    
    # Giả lập dữ liệu trả về phòng trường hợp chưa điền API Key thực tế
    weather_result = {
        "condition": "Rain",
        "temp": 22,
        "text": "Trời đang mưa, 22°C. Chúng tôi khuyên bạn nên mặc nhiều lớp và đi giày chống nước hôm nay."
    }
    
    # Nếu có API Key thật, uncomment đoạn dưới:
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(url)
    #     if response.status_code == 200:
    #         res_data = response.json()
    #         weather_result = {
    #             "condition": res_data["current"]["condition"]["text"],
    #             "temp": int(res_data["current"]["temp_c"]),
    #             "text": f"{res_data['current']['condition']['text']}, {int(res_data['current']['temp_c'])}°C. We recommend layers and waterproof shoes today."
    #         }

    # 3. Lưu vào Redis kèm thời gian hết hạn (TTL) là 15 phút (900 giây)
    redis_client.setex(cache_key, 900, json.dumps(weather_result))
    
    return weather_result
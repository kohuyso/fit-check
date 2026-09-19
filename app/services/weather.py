import json
import random
import datetime
from typing import Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.db.session import redis_client
from app.core.logger import logger

async def get_weather_by_coords(lat: float, lon: float) -> Dict[str, Any]:
    """Lấy thông tin thời tiết hiện tại theo tọa độ kèm bộ nhớ đệm Redis (làm tròn ~10km để tối ưu cache)"""
    cache_key = f"weather:{round(lat, 1)}:{round(lon, 1)}"
    
    cached_data = redis_client.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception:
            pass
    
    weather_result: Optional[Dict[str, Any]] = None
    weather_api_key = settings.WEATHER_API_KEY
    
    if weather_api_key and "your_" not in weather_api_key:
        url = f"https://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={lat},{lon}&lang=vi"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    res_data = response.json()
                    weather_result = {
                        "condition": res_data["current"]["condition"]["text"],
                        "temp": int(res_data["current"]["temp_c"]),
                        "text": f"{res_data['current']['condition']['text']}, {int(res_data['current']['temp_c'])}°C. We recommend layers and comfortable clothes."
                    }
                else:
                    logger.error(f"WeatherAPI Error [{response.status_code}]: {response.text}")
        except Exception as e:
            logger.exception(f"WeatherAPI Exception: {e}")

    if not weather_result:
        weather_options = [
            {
                "condition": "Sunny",
                "temp": 31,
                "text": "Trời đang nắng ráo, 31°C. Thích hợp diện phong cách Casual thoải mái, mang kính râm và giày sneakers."
            },
            {
                "condition": "Rainy",
                "temp": 22,
                "text": "Trời đang có mưa, 22°C. Khuyên bạn nên mặc áo khoác chống nước nhẹ và đi giày chống ẩm."
            },
            {
                "condition": "Cloudy",
                "temp": 26,
                "text": "Trời nhiều mây mát mẻ, 26°C. Rất lý tưởng cho một bộ phối Formal hoặc Smart Casual nhẹ nhàng công sở."
            }
        ]
        weather_result = random.choice(weather_options)
 
    try:
        redis_client.setex(cache_key, 900, json.dumps(weather_result))
    except Exception as e:
        logger.warning(f"Redis cache setex failed for weather: {e}")
        
    return weather_result

def normalize_weather_icon(condition: str | None = "", raw_icon: str | None = "") -> str:
    """Chuẩn hóa icon thời tiết về tên icon Lucide tiêu chuẩn: 'sun', 'cloud', 'rain', 'cloud-sun', 'snow'"""
    cond_lower = condition.lower() if condition else ""
    raw_lower = raw_icon.lower() if raw_icon else ""

    if any(k in cond_lower for k in ["snow", "tuyết", "sleet", "ice", "blizzard"]):
        return "snow"
    if any(k in cond_lower for k in ["rain", "mưa", "drizzle", "shower", "thunder", "storm", "bão"]):
        return "rain"
    if any(k in cond_lower for k in ["partly", "rải rác", "ít mây", "nắng gián đoạn"]):
        return "cloud-sun"
    if any(k in cond_lower for k in ["cloud", "mây", "overcast", "u ám", "sương"]):
        return "cloud"
    if any(k in cond_lower for k in ["sun", "clear", "nắng", "quang", "quang mây"]):
        return "sun"

    if "snow" in raw_lower:
        return "snow"
    if "rain" in raw_lower or "shower" in raw_lower:
        return "rain"
    if "116" in raw_lower or "partly" in raw_lower:
        return "cloud-sun"
    if "113" in raw_lower or "sun" in raw_lower:
        return "sun"
    if "cloud" in raw_lower or "119" in raw_lower or "122" in raw_lower:
        return "cloud"

    return "cloud-sun"

async def get_forecast_by_coords(lat: float = 21.0285, lon: float = 105.8542, days: int = 3) -> List[Dict[str, Any]]:
    """Lấy dự báo thời tiết N ngày tới từ WeatherAPI thực tế kèm bộ nhớ đệm Redis (làm tròn ~10km để tối ưu cache)"""
    cache_key = f"weather_forecast:{round(lat, 1)}:{round(lon, 1)}:{days}"
    
    cached_data = redis_client.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception:
            pass
        
    forecast_results: List[Dict[str, Any]] = []
    weather_api_key = settings.WEATHER_API_KEY
    
    if weather_api_key and "your_" not in weather_api_key:
        url = f"https://api.weatherapi.com/v1/forecast.json?key={weather_api_key}&q={lat},{lon}&days={days}&lang=vi"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    res_data = response.json()
                    raw_days = res_data.get("forecast", {}).get("forecastday", [])
                    for day in raw_days:
                        cond_text = day.get("day", {}).get("condition", {}).get("text", "Mây rải rác")
                        raw_icon = day.get("day", {}).get("condition", {}).get("icon", "")
                        forecast_results.append({
                            "date": day.get("date"),
                            "temp_c": int(day.get("day", {}).get("avgtemp_c", 25)),
                            "condition": cond_text,
                            "icon": normalize_weather_icon(cond_text, raw_icon)
                        })
                else:
                    logger.error(f"WeatherAPI Forecast Error [{response.status_code}]: {response.text}")
        except Exception as e:
            logger.exception(f"WeatherAPI Forecast Exception: {e}")
            
    if not forecast_results:
        today = datetime.date.today()
        base_temp = 25
        conditions = [
            {"cond": "Cloudy", "icon": "cloud", "offset": -1},
            {"cond": "Sunny", "icon": "sun", "offset": 2},
            {"cond": "Partly Cloudy", "icon": "cloud-sun", "offset": 0}
        ]
        for i in range(1, days + 1):
            next_day = today + datetime.timedelta(days=i)
            c_info = conditions[(i - 1) % len(conditions)]
            cond_str = str(c_info["cond"])
            icon_str = str(c_info["icon"])
            offset_val = int(c_info["offset"])
            forecast_results.append({
                "date": next_day.strftime("%Y-%m-%d"),
                "temp_c": base_temp + offset_val,
                "condition": cond_str,
                "icon": normalize_weather_icon(cond_str, icon_str)
            })

    try:
        redis_client.setex(cache_key, 1800, json.dumps(forecast_results))
    except Exception as e:
        logger.warning(f"Redis cache setex failed for forecast: {e}")

    return forecast_results


def get_weather_by_query_sync(location_query: str = "Hanoi", date_str: str = "today") -> Dict[str, Any]:
    """
    Tra cứu thông tin thời tiết đồng bộ theo tên địa điểm hoặc tọa độ (phục vụ LangGraph Tool).
    Hỗ trợ WeatherAPI thực tế kèm bộ nhớ đệm Redis và fallback thông minh.
    """
    clean_loc = (location_query or "Hanoi").strip()
    cache_key = f"weather_query_sync:{clean_loc.lower().replace(' ', '_')}"

    cached_data = redis_client.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception:
            pass

    weather_result: Optional[Dict[str, Any]] = None
    weather_api_key = settings.WEATHER_API_KEY

    if weather_api_key and "your_" not in weather_api_key:
        url = f"https://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={clean_loc}&lang=vi"
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current", {})
                    loc_info = data.get("location", {})
                    resolved_name = loc_info.get("name", clean_loc)
                    temp_c = int(current.get("temp_c", 25))
                    condition_text = current.get("condition", {}).get("text", "Trời quang")
                    humidity = current.get("humidity", 60)
                    
                    weather_result = {
                        "location": resolved_name,
                        "temperature_c": temp_c,
                        "condition": condition_text,
                        "humidity": humidity,
                        "description": f"Thời tiết tại {resolved_name} ({date_str}): {temp_c}°C, {condition_text}, độ ẩm {humidity}%."
                    }
                else:
                    logger.warning(f"WeatherAPI Sync Error [{response.status_code}]: {response.text[:200]}")
        except Exception as e:
            logger.warning(f"WeatherAPI Sync Exception: {e}")

    if not weather_result:
        # Fallback mô phỏng hợp lý theo địa danh
        loc_lower = clean_loc.lower()
        if "dalat" in loc_lower or "đà lạt" in loc_lower or "sapa" in loc_lower:
            temp = 17
            cond = "Mát lạnh, se lạnh về chiều tối"
        elif "hanoi" in loc_lower or "hà nội" in loc_lower:
            temp = 27
            cond = "Nắng nhẹ, nhiều mây"
        elif "hochiminh" in loc_lower or "hồ chí minh" in loc_lower or "saigon" in loc_lower:
            temp = 32
            cond = "Nắng ấm, nhiệt độ cao"
        elif "danang" in loc_lower or "đà nẵng" in loc_lower or "nhatrang" in loc_lower:
            temp = 29
            cond = "Gió biển mát mẻ, nắng nhẹ"
        else:
            temp = 25
            cond = "Thời tiết ôn hòa, dễ chịu"

        weather_result = {
            "location": clean_loc,
            "temperature_c": temp,
            "condition": cond,
            "humidity": 65,
            "description": f"Thời tiết tại {clean_loc} ({date_str}): {temp}°C, {cond}."
        }

    try:
        redis_client.setex(cache_key, 900, json.dumps(weather_result))
    except Exception as e:
        logger.warning(f"Redis cache setex failed for sync weather: {e}")

    return weather_result
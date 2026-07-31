#!/usr/bin/env python3
import asyncio
import logging
import os
import sys

# Đảm bảo import được app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_ai")

async def main():
    print("=" * 60)
    print("🔍 FITCHECK AI ENGINE - DIAGNOSTIC & HEALTH CHECK")
    print("=" * 60)

    from app.services.ai_engine import get_ai_config, generate_outfits

    api_key, api_url, text_model, vision_model = get_ai_config()

    masked_key = f"{api_key[:8]}...{api_key[-4:]}" if api_key else "None (CHƯA CẤU HÌNH API KEY)"
    print(f"🔑 API Key:      {masked_key}")
    print(f"🌐 API URL:      {api_url}")
    print(f"🤖 Text Model:   {text_model}")
    print(f"👁️ Vision Model: {vision_model}")
    print("-" * 60)

    if not api_key:
        print("❌ LỖI: Chưa cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY trong file .env!")
        return

    print("🚀 Đang thử gửi prompt test tới Gemini API...")
    
    class MockItem:
        def __init__(self, id, category, color_code, style_tag):
            self.id = id
            self.category = category
            self.color_code = color_code
            self.style_tag = style_tag

    test_items = [
        MockItem(1, "Shirts", "#FFFFFF", "Formal"),
        MockItem(2, "Pants", "#000000", "Formal"),
        MockItem(3, "Shoes", "#1E293B", "Formal")
    ]

    try:
        outfits = await generate_outfits(1, "Sunny 28°C", "Meeting", test_items)
        if outfits:
            print("✅ KẾT NỐI THÀNH CÔNG!")
            print(f"📦 Số bộ outfit Gemini trả về: {len(outfits)}")
            print(f"📄 Kết quả trả về: {outfits}")
        else:
            print("⚠️ KẾT NỐI THẤT BẠI HOẶC KHÔNG NHẬN ĐƯỢC DỮ LIỆU. Vui lòng kiểm tra log lỗi ở trên.")
    except Exception as e:
        print(f"❌ NGOẠI LỆ TRONG QUÁ TRÌNH THỬ NGHỊỆM: {e}")

if __name__ == "__main__":
    asyncio.run(main())

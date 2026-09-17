from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

def test_ai_test_connection(client: TestClient):
    response = client.get("/api/v1/ai/test-connection")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data

@patch("app.services.ai_engine.generate_style_suggestions", new_callable=AsyncMock)
def test_get_style_suggestions_mocked(mock_gen, client: TestClient, auth_headers: dict):
    mock_gen.return_value = {
        "preferred_style": ["Casual", "Formal"],
        "style_analysis": "Phong cách Smart Casual tối giản kết hợp áo blazer và quần âu.",
        "style_tips": ["Phối áo sơ mi trắng cùng quần âu tối màu", "Layer thêm áo khoác nhẹ"],
        "recommended_looks": [
            {"name": "Look 1", "description": "Navy Blazer + White Shirt", "occasion": "Work"}
        ],
        "suggested_additions": ["Quần Chinos be", "Giày Loafer"]
    }


    response = client.get("/api/v1/ai/style-suggestions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "Smart Casual" in data["style_analysis"]
    assert len(data["recommended_looks"]) == 1
    assert len(data["suggested_additions"]) == 2


@patch("app.services.fashion_agent.run_fashion_stylist_agent", new_callable=AsyncMock)
def test_chat_and_modify_outfit_mocked(mock_agent, client: TestClient, auth_headers: dict):
    mock_agent.return_value = {
        "reply": "Chào bạn! Bộ outfit này rất hợp để dự tiệc cưới ngoài trời.",
        "suggested_outfit_id": None
    }

    payload = {
        "message": "Gợi ý phối đồ đi tiệc cưới ngoài trời",
        "weather": "25°C, Nắng đẹp"
    }
    response = client.post("/api/v1/ai/chat", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "Chào bạn!" in data["reply"]

@patch("app.services.embedding_service.search_wardrobe_hybrid", new_callable=AsyncMock)
@patch("app.services.ai_engine.generate_outfits", new_callable=AsyncMock)
def test_outfit_by_event_mocked(mock_gen, mock_search, client: TestClient, auth_headers: dict):
    # Tạo sẵn 2 item để search_wardrobe_hybrid có thể trả về
    client.post("/api/v1/closet/save", json={
        "image_url": "https://example.com/shirt.png",
        "category": "Shirts",
        "color_code": "#FFFFFF",
        "style_tag": "Formal"
    }, headers=auth_headers)
    client.post("/api/v1/closet/save", json={
        "image_url": "https://example.com/pants.png",
        "category": "Pants",
        "color_code": "#000000",
        "style_tag": "Formal"
    }, headers=auth_headers)

    from app.models.closet import ClothingItem
    item1 = ClothingItem(id=1, category="Shirts", color_code="#FFFFFF", style_tag="Formal", user_id=1, image_url="https://example.com/1.png")
    item2 = ClothingItem(id=2, category="Pants", color_code="#000000", style_tag="Formal", user_id=1, image_url="https://example.com/2.png")

    mock_search.return_value = [item1, item2]
    mock_gen.return_value = [
        {
            "style_type": "Wedding Guest Outfit",
            "items_ids": [1, 2],
            "reasoning": "Classic Black & White formal look"
        }
    ]

    payload = {
        "event_type": "party",
        "weather_condition": "Sunny 25°C"
    }
    response = client.post("/api/v1/ai/outfit-by-event", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "outfit_id" in data
    assert "items" in data

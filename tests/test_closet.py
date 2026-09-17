from fastapi.testclient import TestClient

def test_save_and_get_clothing_item(client: TestClient, auth_headers: dict):
    # 1. Lưu món đồ mới
    item_payload = {
        "image_url": "https://example.com/navy-blazer.png",
        "category": "Jackets",
        "color_name": "Navy Blue",
        "color_code": "#0A192F",
        "style_tag": "Formal",
        "is_ai_fixed": True
    }
    create_res = client.post("/api/v1/closet/save", json=item_payload, headers=auth_headers)
    assert create_res.status_code == 201
    item_id = create_res.json()["item_id"]
    assert item_id is not None

    # 2. Lấy danh sách đồ trong tủ
    list_res = client.get("/api/v1/closet/items", headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    found = any(i["id"] == item_id for i in items)
    assert found

    # 3. Lấy chi tiết món đồ
    detail_res = client.get(f"/api/v1/closet/items/{item_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == item_id
    assert detail["category"] == "Jackets"
    assert detail["color_code"] == "#0A192F"

    # 4. Toggle Favorite
    fav_res = client.post(f"/api/v1/closet/items/{item_id}/favorite", headers=auth_headers)
    assert fav_res.status_code == 200
    assert fav_res.json()["is_favorite"] is True

    # 5. Cập nhật thông tin món đồ
    update_payload = {
        "category": "Blazers",
        "style_tag": "Business Casual",
        "color_name": "Midnight Blue"
    }
    upd_res = client.put(f"/api/v1/closet/items/{item_id}", json=update_payload, headers=auth_headers)
    assert upd_res.status_code == 200
    assert upd_res.json()["category"] == "Blazers"

    # 6. Xóa món đồ
    del_res = client.delete(f"/api/v1/closet/items/{item_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

def test_create_and_bookmark_outfit(client: TestClient, auth_headers: dict):
    # Tạo 2 món đồ làm outfit
    item1_res = client.post("/api/v1/closet/save", json={
        "image_url": "https://example.com/shirt.png",
        "category": "Shirts",
        "color_code": "#FFFFFF",
        "style_tag": "Formal"
    }, headers=auth_headers)
    item1_id = item1_res.json()["item_id"]

    item2_res = client.post("/api/v1/closet/save", json={
        "image_url": "https://example.com/pants.png",
        "category": "Pants",
        "color_code": "#000000",
        "style_tag": "Formal"
    }, headers=auth_headers)
    item2_id = item2_res.json()["item_id"]

    # Tạo Outfit
    outfit_payload = {
        "style_type": "Formal Work Look",
        "item_ids": [item1_id, item2_id]
    }

    create_outfit_res = client.post("/api/v1/closet/outfits", json=outfit_payload, headers=auth_headers)
    assert create_outfit_res.status_code == 201
    outfit_data = create_outfit_res.json()
    outfit_id = outfit_data["outfit_id"]
    assert outfit_id is not None

    # Lấy danh sách Outfits
    outfits_list_res = client.get("/api/v1/closet/outfits", headers=auth_headers)
    assert outfits_list_res.status_code == 200
    assert len(outfits_list_res.json()) >= 1

    # Bookmark outfit
    bm_res = client.post(f"/api/v1/closet/outfits/{outfit_id}/bookmark", headers=auth_headers)
    assert bm_res.status_code == 200
    assert bm_res.json()["is_bookmarked"] is True

from fastapi.testclient import TestClient
from app.models.user import User

def test_register_user_success(client: TestClient):
    payload = {
        "email": "newuser@fitcheck.ai",
        "password": "Password123!",
        "full_name": "New User",
        "preferred_style": ["Minimalist", "Casual"]
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@fitcheck.ai"
    assert data["full_name"] == "New User"
    assert "id" in data

def test_register_duplicate_email(client: TestClient, test_user: User):
    payload = {
        "email": test_user.email,
        "password": "AnyPassword123!",
        "full_name": "Duplicate User"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code in (400, 409)


def test_login_success(client: TestClient, test_user: User):
    form_data = {
        "username": test_user.email,
        "password": "TestPassword123!"
    }
    response = client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password(client: TestClient, test_user: User):
    form_data = {
        "username": test_user.email,
        "password": "WrongPassword!"
    }
    response = client.post("/api/v1/auth/login", data=form_data)
    assert response.status_code in (400, 401)

def test_get_profile_success(client: TestClient, auth_headers: dict, test_user: User):
    response = client.get("/api/v1/auth/profile", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["id"] == test_user.id

def test_get_profile_unauthorized(client: TestClient):
    response = client.get("/api/v1/auth/profile")
    assert response.status_code == 401

def test_change_password_success(client: TestClient, auth_headers: dict):
    payload = {
        "current_password": "TestPassword123!",
        "new_password": "NewSecretPassword456!"
    }
    response = client.post("/api/v1/auth/change-password", json=payload, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_logout(client: TestClient, auth_headers: dict):
    response = client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

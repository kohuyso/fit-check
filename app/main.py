import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
# Import các models để SQLAlchemy nhận diện được cấu trúc trước khi tạo bảng
from app.models import user, closet 
from app.routers import auth
from app.routers import dashboard
from app.routers import closet

# Lệnh thần thánh tự tạo bảng trong PostgreSQL
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FitCheck AI Premium Backend",
    description="Hệ thống API cốt lõi cho ứng dụng quản lý tủ đồ thông minh",
    version="1.0.0"
)

# Cho phép cấu hình danh sách domain qua env, mặc định dùng các cổng dev phổ biến
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:8081", # Thường dùng cho React Native Metro Bundler
        "http://127.0.0.1:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(closet.router)
@app.get("/")
def read_root():
    return {"status": "Database kết nối thành công, các bảng đã được đồng bộ!"}
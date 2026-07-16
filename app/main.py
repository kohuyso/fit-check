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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
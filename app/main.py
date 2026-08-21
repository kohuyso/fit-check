from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from app.core.config import settings
from app.core.logger import logger
from app.database import engine, Base
from app.models import user, closet  # Ensure models are registered before create_all
from app.routers import auth, closet as closet_router, ai, dashboard, explore

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as conn:
            # 1. Kích hoạt extension pgvector nếu database hỗ trợ
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
            except Exception as ext_err:
                logger.warning(f"Could not enable pgvector extension: {ext_err}")
                
            conn.execute(text("ALTER TABLE clothing_items ADD COLUMN IF NOT EXISTS color_name VARCHAR;"))
            conn.execute(text("ALTER TABLE clothing_items ADD COLUMN IF NOT EXISTS is_ai_fixed BOOLEAN DEFAULT TRUE;"))
            conn.execute(text("ALTER TABLE clothing_items ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE clothing_items ADD COLUMN IF NOT EXISTS description_text TEXT;"))
            try:
                conn.execute(text("ALTER TABLE clothing_items ADD COLUMN IF NOT EXISTS embedding vector(768);"))
            except Exception as vec_col_err:
                logger.warning(f"Could not add vector column: {vec_col_err}")
                
            conn.execute(text("ALTER TABLE outfit_combos ADD COLUMN IF NOT EXISTS is_bookmarked BOOLEAN DEFAULT FALSE;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR;"))
            conn.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;"))
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS rating VARCHAR;"))
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS feedback_comment VARCHAR;"))
            conn.execute(text("ALTER TABLE user_calendar ADD COLUMN IF NOT EXISTS notes VARCHAR;"))
            conn.commit()
            
        Base.metadata.create_all(bind=engine)
        logger.info("Database startup migrations & pgvector initialization completed successfully.")
    except Exception as e:
        logger.error(f"Could not run DB startup migrations: {e}")
    yield

app = FastAPI(
    title=settings.APP_TITLE,
    description="Backend API for FitCheck AI - Smart Wardrobe & Outfit Recommendation App",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Configure CORS Middleware
allowed_origins = settings.parsed_allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Xử lý lỗi validation dữ liệu đầu vào (422) và chuyển thành câu thông báo ngắn gọn dễ hiểu"""
    error_messages = []
    for err in exc.errors():
        msg = err.get("msg", "")
        if msg.startswith("Value error, "):
            msg = msg.replace("Value error, ", "")
        loc = err.get("loc", [])
        field = loc[-1] if loc else "dữ liệu"
        if field not in ("body", "query", "path"):
            error_messages.append(f"{field}: {msg}")
        else:
            error_messages.append(msg)
            
    detail_str = " | ".join(error_messages) if error_messages else "Dữ liệu gửi lên không đúng định dạng."
    logger.warning(f"Validation Error 422 on {request.method} {request.url.path}: {detail_str}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": detail_str}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Xử lý thống nhất tất cả các lỗi HTTPException"""
    if exc.status_code >= 500:
        logger.error(f"HTTP {exc.status_code} Error on {request.method} {request.url.path}: {exc.detail}")
    else:
        logger.info(f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Xử lý ngoại lệ không xác định (500) tránh sập ứng dụng hoặc rò rỉ thông tin hệ thống"""
    logger.exception(f"Unhandled Exception 500 on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Đã có lỗi hệ thống xảy ra. Vui lòng thử lại sau."}
    )

# Include Routers
app.include_router(auth.router)
app.include_router(closet_router.router)
app.include_router(ai.router)
app.include_router(dashboard.router)
app.include_router(explore.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": f"Welcome to {settings.APP_TITLE}",
        "docs": "/docs"
    }

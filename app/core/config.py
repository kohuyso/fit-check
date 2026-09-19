import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App General
    APP_TITLE: str = "FitCheck AI API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database & Redis
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/fitcheck_db",
        description="PostgreSQL Connection String"
    )
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Security & Auth
    JWT_SECRET_KEY: str = Field(
        default="fitcheck_secret_key_default_change_me_in_production",
        description="JWT Secret Key for Token Verification"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AI Configuration (Gemini / OpenAI)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_VISION_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"
    OPENAI_API_KEY: Optional[str] = None
    AI_REQUEST_TIMEOUT: float = 30.0

    # Weather & Image Utilities
    WEATHER_API_KEY: Optional[str] = None
    REMOVE_BG_API_KEY: Optional[str] = None

    # MLOps & Observability (LangSmith Tracing)
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "fitcheck-ai-backend"

    # AWS S3 Storage
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_STORAGE_BUCKET_NAME: Optional[str] = None
    AWS_REGION: str = "ap-southeast-1"
    AWS_ENDPOINT_URL: Optional[str] = None
    AWS_S3_CUSTOM_DOMAIN: Optional[str] = None  # CDN/CloudFront or custom public domain

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:8081,exp://localhost:8081,http://localhost:3000,http://127.0.0.1:8081"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    @property
    def parsed_allowed_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

def setup_langsmith_environment(cfg: Optional[Settings] = None) -> bool:
    """
    Tự động đồng bộ các thông số LangSmith Tracing vào os.environ
    để LangGraph / LangChain tự động kích hoạt observability trace.
    """
    active_cfg = cfg or settings
    if active_cfg.LANGCHAIN_TRACING_V2 and active_cfg.LANGCHAIN_API_KEY and "your_" not in active_cfg.LANGCHAIN_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = active_cfg.LANGCHAIN_ENDPOINT
        os.environ["LANGCHAIN_API_KEY"] = active_cfg.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = active_cfg.LANGCHAIN_PROJECT
        return True
    else:
        if not active_cfg.LANGCHAIN_TRACING_V2:
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

settings = Settings()
setup_langsmith_environment(settings)


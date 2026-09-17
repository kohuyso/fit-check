from fastapi import APIRouter
from app.api.v1.endpoints import auth, closet, ai, dashboard, explore

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(closet.router, prefix="/closet", tags=["Closet & AI Scanner"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI Stylist"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard & Recommendation"])
api_router.include_router(explore.router, prefix="/explore", tags=["Explore & Trends"])

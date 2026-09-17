# Backward compatibility shim for app.routers.auth
from app.api.deps import get_token, get_current_user
from app.api.v1.endpoints.auth import router

__all__ = ["router", "get_token", "get_current_user"]
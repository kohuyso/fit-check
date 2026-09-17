# Backward compatibility shim for app.routers.dashboard
from app.api.v1.endpoints.dashboard import router

__all__ = ["router"]
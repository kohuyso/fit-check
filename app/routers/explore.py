# Backward compatibility shim for app.routers.explore
from app.api.v1.endpoints.explore import router

__all__ = ["router"]

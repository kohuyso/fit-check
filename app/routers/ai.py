# Backward compatibility shim for app.routers.ai
from app.api.v1.endpoints.ai import router

__all__ = ["router"]

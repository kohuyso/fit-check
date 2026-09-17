# Backward compatibility shim for app.routers.closet
from app.api.v1.endpoints.closet import router

__all__ = ["router"]
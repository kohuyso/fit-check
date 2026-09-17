from slowapi import Limiter
from slowapi.util import get_remote_address

# Khởi tạo Limiter cho FastAPI dựa trên IP của Client
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"]
)

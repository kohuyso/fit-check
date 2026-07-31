import sys
from pathlib import Path
from loguru import logger

# Thư mục chứa file log
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Xóa handler mặc định của loguru
logger.remove()

# Handler 1: In ra Terminal (stdout)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# Handler 2: Ghi tất cả log vào file logs/app.log
logger.add(
    LOG_DIR / "app.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="INFO",
    rotation="10 MB",
    retention="10 days",
    encoding="utf-8",
)

# Handler 3: Ghi riêng các log LỖI (ERROR) vào file logs/error.log kèm Stack Trace đầy đủ
logger.add(
    LOG_DIR / "error.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
    backtrace=True,
    diagnose=True,
    encoding="utf-8",
)

__all__ = ["logger"]

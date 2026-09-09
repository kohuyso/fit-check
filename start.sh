#!/bin/bash
set -e

# Khởi động Celery Worker chạy ngầm nếu có cấu hình REDIS_URL
if [ -n "$REDIS_URL" ]; then
    echo "Starting Celery worker in background..."
    celery -A app.services.ai_workers.celery_app worker --loglevel=info --concurrency=1 &
fi

# Khởi động Uvicorn Web Server lắng nghe đúng cổng do Render cấp qua biến $PORT
PORT_TO_USE="${PORT:-8000}"
echo "Starting Uvicorn web server on port $PORT_TO_USE..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT_TO_USE"

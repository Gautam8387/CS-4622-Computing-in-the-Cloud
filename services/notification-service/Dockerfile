# ./services/notification-service/Dockerfile
FROM python:3.9-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

COPY services/notification-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# service-specific code
COPY services/notification-service/. .

# common utilities
COPY services/common common

CMD ["celery", "-A", "celery_app.app", "worker", "--loglevel=info", "-n", "notification_worker@%h"]

# ./services/transcoding-service/Dockerfile
FROM python:3.9-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

# install ffmpeg
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

COPY services/transcoding-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# service-specific code
COPY services/transcoding-service/. .

# common utilities
COPY services/common common

CMD ["celery", "-A", "celery_app.app", "worker", "--loglevel=info", "-c", "1", "-n", "transcoding_worker@%h"]

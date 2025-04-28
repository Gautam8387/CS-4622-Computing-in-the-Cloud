# ./services/transcoding-service/Dockerfile
FROM python:3.9-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY common ./common
COPY transcoding-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY transcoding-service/ .

CMD ["celery", "-A", "transcode", "worker", "--loglevel=info"]
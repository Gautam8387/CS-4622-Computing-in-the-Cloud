# ./services/transcoding-service/config.py
import os

from dotenv import load_dotenv

load_dotenv()

# Celery configuration (can also be set via environment in docker-compose)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Redis config for direct use (if needed beyond Celery backend)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


# S3 Configuration (Essential for this service)
S3_BUCKET = os.getenv("S3_BUCKET")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")  # For MinIO/localstack
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")  # For MinIO/localstack
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")  # For MinIO/localstack

# Check essential S3 config
if not S3_BUCKET:
    print("Warning: Transcoding Service S3_BUCKET not configured.")

# Temporary file directory within the container
TEMP_DIR = "/tmp"

# Notification queue/task details (if needed)
# NOTIFICATION_TASK_NAME = 'send_notification'
# NOTIFICATION_QUEUE = 'notifications'

# Archiving settings
ARCHIVE_DELAY_HOURS = int(
    os.getenv("ARCHIVE_DELAY_HOURS", 48)
)  # Delay in hours before archiving

# FFmpeg command templates (can be externalized)
FFMPEG_CMD_VIDEO = (
    "ffmpeg -i {input} -c:v libx264 -preset medium -b:v 1M -c:a aac -b:a 128k {output}"
)
FFMPEG_CMD_AUDIO_FROM_VIDEO = (
    "ffmpeg -i {input} -vn -c:a {codec} -b:a {bitrate} {output}"
)
FFMPEG_CMD_AUDIO_FROM_AUDIO = "ffmpeg -i {input} -c:a {codec} -b:a {bitrate} {output}"

AUDIO_CODECS = {
    "mp3": {"codec": "libmp3lame", "bitrate": "192k"},
    "aac": {"codec": "aac", "bitrate": "128k"},
    "wav": {"codec": "pcm_s16le", "bitrate": None},  # Bitrate not applicable for PCM
    "flac": {"codec": "flac", "bitrate": None},  # FLAC is lossless
}

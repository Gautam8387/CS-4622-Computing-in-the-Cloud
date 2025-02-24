# ./services/common/queue.py
import redis
from celery import Celery

from services.api_gateway.config import REDIS_URL

celery = Celery("transcoding_tasks", broker=REDIS_URL, backend=REDIS_URL)
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


def add_transcoding_job(filename, email, output_format):
    s3_key = f"raw/{filename}"
    task = celery.send_task("transcode_file", args=[s3_key, email, output_format])
    return task.id

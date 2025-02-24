from celery import Celery
from services.api_gateway.config import REDIS_URL

celery = Celery('transcoding_tasks', broker=REDIS_URL, backend=REDIS_URL)

def add_transcoding_job(s3_key, email):
    task = celery.send_task('transcode_file', args=[s3_key, email])
    return task.id
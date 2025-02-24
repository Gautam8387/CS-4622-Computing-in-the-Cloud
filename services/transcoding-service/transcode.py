import os
import subprocess
from datetime import datetime, timedelta

import boto3
from common import celery, get_s3_url, redis_client, upload_to_s3

from services.transcoding_service.config import REDIS_URL, S3_BUCKET

celery = celery  # Use the shared Celery instance
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
)


@celery.task(name="transcode_file")
def transcode_file(s3_key, email, output_format):
    # Download file from S3
    input_file = f"/tmp/{s3_key.split('/')[-1]}"
    with open(input_file, "wb") as f:
        s3_client.download_fileobj(S3_BUCKET, s3_key, f)

    # Determine input format and transcoding command
    filename = s3_key.split("/")[-1]
    input_format = filename.rsplit(".", 1)[1].lower() if "." in filename else "unknown"
    output_file = f"/tmp/{filename.rsplit('.', 1)[0]}.{output_format}"

    # FFmpeg command based on output format
    cmd = ["ffmpeg", "-i", input_file]
    if output_format in {"mp4", "avi", "mov", "mkv", "webm"}:  # Video formats
        cmd.extend(["-c:v", "libx264", "-b:v", "1M", "-c:a", "aac", output_file])
    elif output_format in {
        "mp3",
        "wav",
        "flac",
        "aac",
    }:  # Audio formats (extract audio from video if video)
        if input_format in {"mp4", "avi", "mov", "mkv", "webm"}:
            cmd.extend(
                [
                    "-vn",
                    "-acodec",
                    {
                        "mp3": "libmp3lame",
                        "wav": "pcm_s16le",
                        "flac": "flac",
                        "aac": "aac",
                    }[output_format],
                    output_file,
                ]
            )
        else:
            cmd.extend(
                [
                    "-acodec",
                    {
                        "mp3": "libmp3lame",
                        "wav": "pcm_s16le",
                        "flac": "flac",
                        "aac": "aac",
                    }[output_format],
                    output_file,
                ]
            )
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    subprocess.run(cmd, check=True)

    # Upload result to S3
    output_key = f"processed/{filename.rsplit('.', 1)[0]}.{output_format}"
    with open(output_file, "rb") as f:
        upload_to_s3(f, output_key)

    # Generate download URL
    download_url = get_s3_url(output_key)

    # Trigger notification
    celery.send_task("send_notification", args=[email, download_url])

    # Update job status in Redis
    job_id = celery.current_task.request.id
    user = email  # Use email as user identifier
    jobs_key = f"jobs:{user}"
    job_data = redis_client.lrange(jobs_key, 0, -1)[0].decode("utf-8")  # Get the job
    job_dict = eval(job_data)
    job_dict.update({"status": "completed", "download_url": download_url})
    redis_client.lset(jobs_key, 0, str(job_dict))

    # Schedule archiving after 24 hours
    celery.send_task(
        "archive_file", args=[output_key], eta=datetime.utcnow() + timedelta(hours=24)
    )

    return {"status": "completed", "output_url": download_url}


@celery.task(name="archive_file")
def archive_file(s3_key):
    # For local testing (MinIO), just log or delete (Glacier not supported)
    print(f"Simulating move of {s3_key} to cold storage (AWS S3 Glacier)")

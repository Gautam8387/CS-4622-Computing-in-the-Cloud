######################################################################################################
# import subprocess
# from common import celery, get_s3_url, upload_to_s3  # Updated import
# from services.transcoding_service.config import REDIS_URL

# celery = celery  # Use the shared Celery instance

# @celery.task(name='transcode_file')
# def transcode_file(s3_key):
#     # Download from S3 (simplified, assumes local access in Docker)
#     input_file = f"/tmp/{s3_key.split('/')[-1]}"
#     output_file = input_file.rsplit('.', 1)[0] + '_converted.mp4'
    
#     # FFmpeg command (example: convert to MP4)
#     cmd = ['ffmpeg', '-i', input_file, '-c:v', 'libx264', '-b:v', '1M', output_file]
#     subprocess.run(cmd, check=True)
    
#     # Upload result back to S3
#     output_key = f"processed/{output_file.split('/')[-1]}"
#     with open(output_file, 'rb') as f:
#         upload_to_s3(f, output_key)
    
#     return {'status': 'completed', 'output_url': get_s3_url(output_key)}
######################################################################################################
import subprocess
from datetime import datetime, timedelta
from common import celery, get_s3_url, upload_to_s3
from services.transcoding_service.config import REDIS_URL, S3_BUCKET
import boto3
import os

celery = celery  # Use the shared Celery instance
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('S3_ENDPOINT_URL', 'https://s3.amazonaws.com'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY')
)

@celery.task(name='transcode_file')
def transcode_file(s3_key, email):
    # Download file from S3
    input_file = f"/tmp/{s3_key.split('/')[-1]}"
    with open(input_file, 'wb') as f:
        s3_client.download_fileobj(S3_BUCKET, s3_key, f)
    
    # Transcode
    output_file = input_file.rsplit('.', 1)[0] + '_converted.mp4'
    cmd = ['ffmpeg', '-i', input_file, '-c:v', 'libx264', '-b:v', '1M', output_file]
    subprocess.run(cmd, check=True)
    
    # Upload result to S3
    output_key = f"processed/{output_file.split('/')[-1]}"
    with open(output_file, 'rb') as f:
        upload_to_s3(f, output_key)
    
    # Generate download URL
    download_url = get_s3_url(output_key)
    
    # Trigger notification
    celery.send_task('send_notification', args=[email, download_url])
    
    # Schedule archiving after 48 hours (simulated for local, AWS handles via lifecycle)
    celery.send_task('archive_file', args=[output_key], eta=datetime.utcnow() + timedelta(hours=24))
    
    return {'status': 'completed', 'output_url': download_url}

@celery.task(name='archive_file')
def archive_file(s3_key):
    # For local testing (MinIO), just log or delete (Glacier not supported)
    # In AWS, this is handled by S3 lifecycle, so this is a no-op
    print(f"Simulating move of {s3_key} to cold storage (AWS S3 Glacier)")
    # Optionally delete the local file if testing cleanup:
    # s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
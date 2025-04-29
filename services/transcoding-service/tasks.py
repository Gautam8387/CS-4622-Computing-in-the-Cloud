# ./services/transcoding-service/tasks.py
import logging
import os
import subprocess
import tempfile
import time

import redis
from botocore.exceptions import ClientError
from celery import current_app, shared_task

# Important: Ensure 'common' is accessible in PYTHONPATH
try:
    from common import storage
except ImportError:
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from common import storage

# Logger instance
logger = logging.getLogger(__name__)

# --- Configuration (from environment loaded by celery_app) ---
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
S3_PROCESSED_PREFIX = os.environ.get("S3_PROCESSED_PREFIX", "processed/")
NOTIFICATION_TASK_NAME = os.environ.get(
    "NOTIFICATION_TASK_NAME", "notification.tasks.send_notification_email"
)  # Name of the notification task

# Redis Connection Pool (more efficient for frequent connections)
try:
    # Use decode_responses=True for easier handling of hash values
    redis_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
    logger.info("Redis connection pool created.")
except Exception as e:
    logger.error(f"Failed to create Redis connection pool: {e}")
    redis_pool = None


# --- Helper Functions ---
def get_redis_connection():
    """Gets a Redis connection from the pool."""
    if not redis_pool:
        raise ConnectionError("Redis connection pool is not available.")
    return redis.Redis(connection_pool=redis_pool)


def update_job_status(
    job_id, status, error_message=None, output_key=None, download_url=None
):
    """Updates the job status and details in Redis."""
    try:
        r = get_redis_connection()
        job_key = f"job:{job_id}"
        update_data = {"status": status, "last_updated": int(time.time())}
        if error_message:
            # Limit error message length stored in Redis
            update_data["error"] = str(error_message)[:1024]
        if output_key:
            update_data["output_s3_key"] = output_key
        if download_url:
            update_data["download_url"] = download_url

        r.hset(job_key, mapping=update_data)
        logger.info(f"Job {job_id}: Status updated to {status} in Redis.")
        # If COMPLETED or FAILED, maybe set an expiry on the main job key if desired?
        # r.expire(job_key, 86400 * 7) # e.g., expire after 7 days
    except redis.RedisError as e:
        logger.error(f"Job {job_id}: Redis error updating status to {status}: {e}")
    except ConnectionError as e:
        logger.error(
            f"Job {job_id}: Could not get Redis connection to update status: {e}"
        )
    except Exception as e:
        logger.error(f"Job {job_id}: Unexpected error updating Redis status: {e}")


def build_ffmpeg_command(input_path, output_path, output_format):
    """Constructs the FFmpeg command line."""
    # Basic command, can be expanded with more options/presets
    command = [
        "ffmpeg",
        "-i",
        input_path,  # Input file
        "-y",  # Overwrite output file if exists
        "-hide_banner",  # Suppress unnecessary banner info
        "-loglevel",
        "error",  # Log only errors to stderr
    ]

    # Add format-specific options if needed (example)
    if output_format == "mp4":
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "23",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
            ]
        )
    elif output_format == "webm":
        command.extend(
            [
                "-c:v",
                "libvpx-vp9",
                "-crf",
                "30",
                "-b:v",
                "0",
                "-c:a",
                "libopus",
                "-b:a",
                "128k",
            ]
        )
    elif output_format == "mp3":
        command.extend(
            ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]
        )  # VBR quality setting 2
    elif output_format == "aac":
        command.extend(["-vn", "-c:a", "aac", "-b:a", "128k"])
    # Add more format handling...
    else:
        # Default: let FFmpeg try to figure it out based on extension
        logger.warning(
            f"Using default FFmpeg codec selection for format: {output_format}"
        )
        pass

    command.append(output_path)  # Output file
    return command


# --- Celery Task ---
@shared_task(bind=True, max_retries=2, default_retry_delay=30, acks_late=True)
def transcode_media(self, payload):
    """
    Celery task to download, transcode, upload media, and update status.

    Args:
        payload (dict): A dictionary containing job details:
            - job_id (str)
            - input_s3_key (str)
            - output_format (str)
            - user_email (str)
            - notification_email (str)
            - original_filename (str)
    """
    job_id = payload.get("job_id")
    input_s3_key = payload.get("input_s3_key")
    output_format = payload.get("output_format")
    notification_email = payload.get("notification_email")
    original_filename = payload.get("original_filename")

    if not all([job_id, input_s3_key, output_format]):
        logger.error(f"Task received with missing essential payload data: {payload}")
        # Do not retry, data is fundamentally missing
        update_job_status(
            job_id, "FAILED", error_message="Internal error: Missing essential job data"
        )
        return {"status": "failed", "error": "Missing essential job data"}

    logger.info(
        f"Job {job_id}: Starting transcoding task for {input_s3_key} -> {output_format}"
    )
    update_job_status(job_id, "PROCESSING")

    # Use a temporary directory for downloaded/processed files
    with tempfile.TemporaryDirectory() as temp_dir:
        local_input_path = os.path.join(
            temp_dir, os.path.basename(input_s3_key)
        )  # Use S3 key basename for temp file
        local_output_filename = (
            f"{job_id}.{output_format}"  # Use job_id for unique output name
        )
        local_output_path = os.path.join(temp_dir, local_output_filename)
        output_s3_key = f"{S3_PROCESSED_PREFIX.strip('/')}/{local_output_filename}"  # Construct output S3 key

        # 1. Download Input File from S3
        try:
            logger.info(
                f"Job {job_id}: Downloading {input_s3_key} to {local_input_path}"
            )
            start_time = time.time()
            storage.download_file(input_s3_key, local_input_path)
            download_time = time.time() - start_time
            logger.info(
                f"Job {job_id}: Download complete in {download_time:.2f} seconds."
            )
        except (ClientError, Exception) as e:
            logger.error(f"Job {job_id}: Failed to download {input_s3_key}: {e}")
            update_job_status(
                job_id, "FAILED", error_message=f"Failed to download input file: {e}"
            )
            # Optionally retry for specific S3 errors? For now, fail permanently.
            return {"status": "failed", "error": f"Download failed: {e}"}

        # 2. Run FFmpeg
        try:
            ffmpeg_command = build_ffmpeg_command(
                local_input_path, local_output_path, output_format
            )
            logger.info(f"Job {job_id}: Executing FFmpeg: {' '.join(ffmpeg_command)}")
            start_time = time.time()
            # Use subprocess.run, capture stderr
            result = subprocess.run(
                ffmpeg_command, capture_output=True, text=True, check=False
            )  # check=False allows us to inspect errors
            ffmpeg_time = time.time() - start_time

            if result.returncode != 0:
                # FFmpeg failed
                error_log = result.stderr or "No error output captured"
                logger.error(
                    f"Job {job_id}: FFmpeg failed (code {result.returncode}) in {ffmpeg_time:.2f}s. Error:\n{error_log}"
                )
                update_job_status(
                    job_id,
                    "FAILED",
                    error_message=f"FFmpeg error (code {result.returncode}): {error_log[:500]}",
                )  # Store truncated error
                return {"status": "failed", "error": f"FFmpeg error: {error_log[:500]}"}
            else:
                logger.info(
                    f"Job {job_id}: FFmpeg completed successfully in {ffmpeg_time:.2f} seconds."
                )

        except FileNotFoundError:
            logger.error(
                f"Job {job_id}: FFmpeg command not found. Is FFmpeg installed in the container?"
            )
            update_job_status(
                job_id, "FAILED", error_message="Internal error: FFmpeg not found"
            )
            return {"status": "failed", "error": "FFmpeg not found"}
        except Exception as e:
            logger.error(f"Job {job_id}: Unexpected error during FFmpeg execution: {e}")
            update_job_status(
                job_id, "FAILED", error_message=f"Unexpected transcoding error: {e}"
            )
            return {"status": "failed", "error": f"Unexpected transcoding error: {e}"}

        # 3. Upload Processed File to S3
        try:
            if (
                not os.path.exists(local_output_path)
                or os.path.getsize(local_output_path) == 0
            ):
                logger.error(
                    f"Job {job_id}: FFmpeg reported success, but output file '{local_output_path}' is missing or empty."
                )
                update_job_status(
                    job_id,
                    "FAILED",
                    error_message="Internal error: Transcoded file missing after successful FFmpeg run.",
                )
                return {"status": "failed", "error": "Transcoded file missing"}

            logger.info(
                f"Job {job_id}: Uploading {local_output_path} to {output_s3_key}"
            )
            start_time = time.time()
            storage.upload_file(local_output_path, output_s3_key)
            upload_time = time.time() - start_time
            logger.info(f"Job {job_id}: Upload complete in {upload_time:.2f} seconds.")
        except (ClientError, Exception) as e:
            logger.error(
                f"Job {job_id}: Failed to upload processed file {output_s3_key}: {e}"
            )
            update_job_status(
                job_id, "FAILED", error_message=f"Failed to upload processed file: {e}"
            )
            # Retry might be appropriate here for temporary S3 issues
            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                logger.error(
                    f"Job {job_id}: Max retries exceeded for S3 upload failure."
                )
                return {
                    "status": "failed",
                    "error": f"Upload failed after retries: {e}",
                }
            except Exception as retry_exc:
                logger.error(
                    f"Job {job_id}: Error during retry mechanism for S3 upload: {retry_exc}"
                )
                return {
                    "status": "failed",
                    "error": f"Error during retry mechanism for S3 upload: {retry_exc}",
                }

        # 4. Generate Download URL (Optional but good to store with job)
        download_url = None
        try:
            download_url = storage.create_presigned_url(output_s3_key)
            logger.info(f"Job {job_id}: Generated download URL for {output_s3_key}")
        except (ClientError, Exception) as e:
            logger.warning(
                f"Job {job_id}: Failed to generate pre-signed URL for {output_s3_key}, proceeding without it: {e}"
            )
            # Don't fail the whole job, just log the warning. Notification will be sent without URL in metadata.

        # 5. Update Status to COMPLETED in Redis
        update_job_status(
            job_id, "COMPLETED", output_key=output_s3_key, download_url=download_url
        )

        # 6. Trigger Notification Task
        if notification_email and NOTIFICATION_TASK_NAME:
            try:
                notification_payload = {
                    "job_id": job_id,
                    "notification_email": notification_email,
                    "original_filename": original_filename,
                    "output_format": output_format,
                    "output_s3_key": output_s3_key,  # Send the key so notification service can generate its own URL
                }
                current_app.send_task(
                    NOTIFICATION_TASK_NAME, args=[notification_payload]
                )
                logger.info(
                    f"Job {job_id}: Notification task sent for {notification_email}"
                )
            except Exception as e:
                # Log error but don't fail the transcoding task itself
                logger.error(f"Job {job_id}: Failed to send notification task: {e}")
        else:
            logger.info(
                f"Job {job_id}: Skipping notification task (no email or task name configured)."
            )

        logger.info(f"Job {job_id}: Transcoding task finished successfully.")
        return {"status": "success", "output_s3_key": output_s3_key}

    # End of `with tempfile.TemporaryDirectory()` - cleanup happens automatically

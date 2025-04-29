# ./services/api-gateway/app.py
import logging
import os
import time
import uuid
from functools import wraps

import jwt  # PyJWT
import redis
import requests
from celery import Celery

# from dotenv import dotenv_values
from flask import Flask, g, jsonify, request  # g for storing user info per request
from werkzeug.utils import secure_filename  # For getting original filename safely

# --- Configuration ---
# Load .env file from project root
config = {
    # **dotenv_values(".env"),  # load development variables
    **os.environ,  # override loaded values with environment variables
}

app = Flask(__name__)

# Logging Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Redis Connection (for job metadata & user history)
try:
    redis_client = redis.Redis.from_url(
        config.get("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,  # Decode responses to strings
    )
    redis_client.ping()  # Check connection
    logger.info("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    redis_client = None  # Handle gracefully later if needed

# Celery Configuration (only need broker to send tasks)
# Result backend interaction happens via redis_client or AsyncResult if needed directly
celery_app = Celery(
    "tasks", broker=config.get("CELERY_BROKER_URL", "redis://redis:6379/0")
)
# Optional: Configure result backend if you need to query AsyncResult directly here
# celery_app.conf.update(result_backend=config.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'))

# Service URLs
UPLOAD_SERVICE_URL = config.get("UPLOAD_SERVICE_URL", "http://upload-service:5003")

# JWT Configuration
JWT_SECRET_KEY = config.get("JWT_SECRET_KEY", "default-fallback-secret-key-change-me")
JWT_ALGORITHM = config.get("JWT_ALGORITHM", "HS256")

# --- Constants ---
ALLOWED_EXTENSIONS = {
    "mp4",
    "avi",
    "mov",
    "mkv",
    "webm",
    "mp3",
    "wav",
    "flac",
    "aac",
}  # Example, refine as needed
SUPPORTED_OUTPUT_FORMATS = {
    "mp4",
    "webm",
    "avi",
    "mov",
    "mkv",
    "mp3",
    "wav",
    "flac",
    "aac",
}
MAX_JOB_HISTORY = 10  # Number of recent job IDs to keep per user


# --- Helper Functions ---
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_task_result(task_id):
    """Get task result directly from Celery backend (Redis)."""
    if not redis_client:
        return {"status": "ERROR", "error": "Redis connection unavailable"}
    try:
        # Celery stores results under keys like 'celery-task-meta-<task_id>'
        result_key = f"celery-task-meta-{task_id}"
        raw_data = redis_client.get(result_key)
        if raw_data:
            # Data is stored as a JSON string
            import json

            data = json.loads(raw_data)
            # Map Celery states to our application states
            status_map = {
                "PENDING": "PENDING",
                "STARTED": "PROCESSING",  # Celery's STARTED maps to our PROCESSING
                "SUCCESS": "COMPLETED",  # Celery's SUCCESS maps to our COMPLETED
                "FAILURE": "FAILED",  # Celery's FAILURE maps to our FAILED
                "RETRY": "PROCESSING",  # Treat retry as still processing
                "REVOKED": "FAILED",  # Treat revoked as failed
            }
            app_status = status_map.get(data.get("status", "PENDING"), "PENDING")

            result_payload = {
                "status": app_status,
                "job_id": task_id,
            }
            # If failed, include the error message (result field might contain exception info)
            if app_status == "FAILED":
                # Celery stores exception info in 'result' or 'traceback'
                error_info = data.get("result")  # Often contains exception repr
                if isinstance(error_info, dict) and "exc_message" in error_info:
                    result_payload["error"] = str(error_info["exc_message"])
                elif error_info:
                    result_payload["error"] = str(error_info)
                else:
                    result_payload["error"] = data.get("traceback", "Unknown error")

            return result_payload
        else:
            # If key doesn't exist, task might not have started or expired
            # Check our own metadata store as a fallback
            return {
                "status": "UNKNOWN",
                "job_id": task_id,
                "error": "Task status not found in backend",
            }

    except Exception as e:
        logger.error(f"Error fetching task result for {task_id} from backend: {e}")
        return {
            "status": "ERROR",
            "job_id": task_id,
            "error": f"Internal error fetching status: {e}",
        }


# --- Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
            else:
                logger.warning("Malformed Authorization header received.")
                return jsonify({"error": "Malformed Authorization header"}), 401

        if not token:
            logger.warning("Authorization token is missing.")
            return jsonify({"error": "Authorization token is missing"}), 401

        try:
            # Validate the token using the secret key
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            # Store user data in Flask's 'g' object for access within the request context
            g.current_user = {
                "email": data.get("email"),
                "name": data.get("name"),
                # Add other claims as needed
            }
            if not g.current_user.get("email"):
                logger.error("JWT is valid but missing 'email' claim.")
                return jsonify({"error": "Invalid token claims (missing email)"}), 401
            logger.info(f"Authenticated user: {g.current_user['email']}")

        except jwt.ExpiredSignatureError:
            logger.warning("Expired token received.")
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token received: {e}")
            return jsonify({"error": f"Token is invalid: {e}"}), 401
        except Exception as e:
            logger.error(f"Error during token decoding: {e}")
            return jsonify(
                {"error": "Internal server error during authentication"}
            ), 500

        return f(*args, **kwargs)

    return decorated


# --- Routes ---


@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    # Could add checks for Redis, Celery broker connections here
    return jsonify({"status": "healthy"}), 200


@app.route("/upload", methods=["POST"])
@token_required
def upload_file():
    """
    Handles file upload, forwards to upload-service, and queues transcoding task.
    Requires JWT authentication.
    """
    user_email = g.current_user["email"]
    logger.info(f"Upload request received from user: {user_email}")

    if "media_file" not in request.files:
        logger.warning("No 'media_file' part in the request.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["media_file"]
    output_format = request.form.get("output_format")
    notification_email = request.form.get(
        "email", user_email
    )  # Default to user's login email

    if not file or file.filename == "":
        logger.warning("No selected file.")
        return jsonify({"error": "No selected file"}), 400

    if not output_format or output_format.lower() not in SUPPORTED_OUTPUT_FORMATS:
        logger.warning(f"Invalid or missing output format: {output_format}")
        return jsonify(
            {
                "error": f"Invalid or missing output_format. Supported: {', '.join(SUPPORTED_OUTPUT_FORMATS)}"
            }
        ), 400

    original_filename = secure_filename(file.filename)  # Sanitize filename

    # Optional: Check file extension here if needed, though FFmpeg is robust
    # if not allowed_file(original_filename):
    #     logger.warning(f"File type not allowed: {original_filename}")
    #     return jsonify({'error': 'File type not allowed'}), 400

    logger.info(
        f"Processing upload: Filename='{original_filename}', Format='{output_format}', User='{user_email}'"
    )

    # 1. Forward file to Upload Service
    try:
        # Important: Pass the file stream directly using 'files' parameter
        files_to_forward = {
            "media_file": (original_filename, file.stream, file.mimetype)
        }
        logger.info(f"Forwarding file to upload service at {UPLOAD_SERVICE_URL}/upload")
        upload_response = requests.post(
            f"{UPLOAD_SERVICE_URL}/upload",
            files=files_to_forward,
            timeout=60,  # Add a timeout
        )
        upload_response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        upload_data = upload_response.json()
        input_s3_key = upload_data.get("s3_key")

        if not input_s3_key:
            logger.error("Upload service did not return an S3 key.")
            return jsonify({"error": "Failed to store uploaded file"}), 500

        logger.info(
            f"File successfully uploaded by upload-service. S3 Key: {input_s3_key}"
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Error contacting upload service: {e}")
        return jsonify(
            {"error": f"Upload service unavailable: {e}"}
        ), 503  # Service Unavailable
    except Exception as e:
        logger.error(f"Unexpected error during upload forwarding: {e}")
        return jsonify({"error": f"Internal error during upload: {e}"}), 500

    # 2. Generate Job ID and Queue Transcoding Task
    job_id = str(uuid.uuid4())
    task_payload = {
        "job_id": job_id,
        "input_s3_key": input_s3_key,
        "output_format": output_format.lower(),
        "user_email": user_email,  # User who initiated
        "notification_email": notification_email,  # Email for notification
        "original_filename": original_filename,
    }

    try:
        # --- MODIFIED: Specify the queue ---
        celery_app.send_task(
            "transcoding.tasks.transcode_media",
            args=[task_payload],
            task_id=job_id,
            queue="transcoding_queue",  # <--- ADD THIS
        )
        # --- END MODIFICATION ---
        logger.info(
            f"Transcoding task queued successfully to 'transcoding_queue'. Job ID: {job_id}"
        )

    except Exception as e:
        logger.error(f"Failed to queue transcoding task for Job ID {job_id}: {e}")
        return jsonify({"error": f"Failed to queue transcoding job: {e}"}), 500

    # 3. Store Initial Job Metadata in Redis
    if redis_client:
        try:
            job_metadata_key = f"job:{job_id}"
            initial_metadata = {
                "job_id": job_id,
                "user_email": user_email,
                "notification_email": notification_email,
                "status": "PENDING",  # Initial status
                "input_s3_key": input_s3_key,
                "output_format": output_format.lower(),
                "original_filename": original_filename,
                "timestamp": int(time.time()),  # Unix timestamp
            }
            redis_client.hset(job_metadata_key, mapping=initial_metadata)
            # Optional: Set an expiry for job metadata? Maybe not, keep for history.

            # Add job to user's history list (most recent first)
            user_history_key = f"user:{user_email}:jobs"
            # Push job ID to the left (front) of the list
            redis_client.lpush(user_history_key, job_id)
            # Trim the list to keep only the last N jobs
            redis_client.ltrim(user_history_key, 0, MAX_JOB_HISTORY - 1)

            logger.info(f"Initial metadata stored in Redis for Job ID: {job_id}")

        except redis.exceptions.RedisError as e:
            logger.error(
                f"Redis error storing metadata/history for Job ID {job_id}: {e}"
            )
            # Continue, but log the error. The job is queued, but history/status might be incomplete initially.
            # The worker *should* update the status later anyway.
        except Exception as e:
            logger.error(
                f"Non-Redis error storing metadata/history for Job ID {job_id}: {e}"
            )

    # 4. Return Job ID to Client
    return jsonify(
        {"job_id": job_id, "message": "File upload received, transcoding queued."}
    ), 202  # Accepted


@app.route("/status/<job_id>", methods=["GET"])
@token_required
def get_job_status(job_id):
    """Gets the status of a specific transcoding job. Requires JWT authentication."""
    user_email = g.current_user["email"]
    logger.info(f"Status request for Job ID: {job_id} from User: {user_email}")

    if not redis_client:
        return jsonify({"error": "Backend service unavailable (Redis)"}), 503

    # 1. Check our primary metadata store first
    job_metadata_key = f"job:{job_id}"
    try:
        metadata = redis_client.hgetall(job_metadata_key)
        if not metadata:
            logger.warning(f"Job metadata not found in Redis for Job ID: {job_id}")
            # Optionally check Celery backend as fallback, but metadata should be source of truth
            # For now, return 404 if not in our metadata store
            return jsonify({"error": "Job not found"}), 404

        # Security Check: Ensure the requesting user owns this job
        if metadata.get("user_email") != user_email:
            logger.warning(
                f"Access denied: User {user_email} attempting to access job {job_id} owned by {metadata.get('user_email')}"
            )
            return jsonify({"error": "Access denied to this job"}), 403

        # 2. If status is PENDING or PROCESSING in metadata, double-check Celery backend
        current_status = metadata.get("status", "UNKNOWN")
        if current_status in ["PENDING", "PROCESSING", "UNKNOWN"]:
            logger.info(
                f"Checking Celery backend for potentially updated status for Job ID: {job_id}"
            )
            backend_result = get_task_result(job_id)  # Use the helper
            backend_status = backend_result.get("status")

            if (
                backend_status
                and backend_status != "UNKNOWN"
                and backend_status != current_status
            ):
                logger.info(
                    f"Celery backend status ({backend_status}) differs from metadata ({current_status}) for Job ID: {job_id}. Updating metadata."
                )
                metadata["status"] = backend_status  # Update local copy
                # Persist the updated status back to Redis metadata
                redis_client.hset(job_metadata_key, "status", backend_status)
                if backend_status == "FAILED" and "error" in backend_result:
                    metadata["error"] = backend_result["error"]
                    redis_client.hset(
                        job_metadata_key, "error", backend_result["error"]
                    )

        # 3. Prepare response based on metadata (possibly updated from backend check)
        response_payload = {
            "job_id": job_id,
            "status": metadata.get("status", "UNKNOWN"),
            "timestamp": int(metadata.get("timestamp", 0)),
            "original_filename": metadata.get("original_filename"),
            "output_format": metadata.get("output_format"),
        }
        if metadata.get("status") == "FAILED":
            response_payload["error"] = metadata.get("error", "Unknown error")
        if metadata.get("status") == "COMPLETED":
            response_payload["download_url"] = metadata.get(
                "download_url"
            )  # Worker should add this

        return jsonify(response_payload), 200

    except redis.exceptions.RedisError as e:
        logger.error(f"Redis error checking status for Job ID {job_id}: {e}")
        return jsonify({"error": "Backend service unavailable (Redis)"}), 503
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}")
        return jsonify({"error": f"Internal server error fetching status: {e}"}), 500


@app.route("/jobs", methods=["GET"])
@token_required
def get_job_history():
    """Gets the recent job history for the authenticated user."""
    user_email = g.current_user["email"]
    logger.info(f"Fetching job history for user: {user_email}")

    if not redis_client:
        return jsonify({"error": "Backend service unavailable (Redis)"}), 503

    try:
        user_history_key = f"user:{user_email}:jobs"
        # Get all job IDs from the user's list (up to MAX_JOB_HISTORY)
        job_ids = redis_client.lrange(user_history_key, 0, -1)

        jobs_details = []
        if job_ids:
            # Use Redis pipeline for efficient fetching of multiple hashes
            pipe = redis_client.pipeline()
            for job_id in job_ids:
                pipe.hgetall(f"job:{job_id}")
            results = pipe.execute()

            for job_id, metadata in zip(job_ids, results):
                if metadata:  # Check if hash exists (it might have expired or failed to be created)
                    # Convert timestamp back to int if needed
                    if "timestamp" in metadata:
                        try:
                            metadata["timestamp"] = int(metadata["timestamp"])
                        except (ValueError, TypeError):
                            metadata["timestamp"] = 0  # Or handle error

                    # Ensure essential fields exist
                    job_detail = {
                        "job_id": metadata.get(
                            "job_id", job_id
                        ),  # Use original ID as fallback
                        "status": metadata.get("status", "UNKNOWN"),
                        "timestamp": metadata.get("timestamp"),
                        "original_filename": metadata.get("original_filename"),
                        "output_format": metadata.get("output_format"),
                        "input_s3_key": metadata.get(
                            "input_s3_key"
                        ),  # May not want to expose this?
                        "download_url": metadata.get(
                            "download_url"
                        ),  # Only present if completed
                        "error": metadata.get("error"),  # Only present if failed
                    }
                    jobs_details.append(job_detail)
                else:
                    logger.warning(
                        f"Metadata for job ID {job_id} listed in user {user_email}'s history not found in Redis."
                    )
                    # Optionally include a placeholder or skip
                    jobs_details.append(
                        {
                            "job_id": job_id,
                            "status": "UNKNOWN",
                            "error": "Metadata not found",
                        }
                    )

        logger.info(f"Returning {len(jobs_details)} jobs for user {user_email}")
        return jsonify(jobs_details), 200

    except redis.exceptions.RedisError as e:
        logger.error(f"Redis error fetching job history for user {user_email}: {e}")
        return jsonify({"error": "Backend service unavailable (Redis)"}), 503
    except Exception as e:
        logger.error(f"Error fetching job history for {user_email}: {e}")
        return jsonify({"error": f"Internal server error fetching history: {e}"}), 500


if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible within Docker network
    # Port 5001 as per docker-compose example
    app.run(host="0.0.0.0", port=5001, debug=config.get("FLASK_ENV") == "development")

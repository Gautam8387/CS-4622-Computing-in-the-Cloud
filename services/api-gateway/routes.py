# ./services/api-gateway/routes.py
import datetime
import requests
import jwt

from flask import request, jsonify, g # Use current_app for config
from werkzeug.utils import secure_filename
from celery.result import AsyncResult # To check task status

from common import add_transcoding_job, setup_logger # Keep add_transcoding_job

logger = setup_logger()

def init_routes(app_instance):
    # Use app_instance passed from app.py
    # JWT Secret Key for validation
    JWT_SECRET_KEY = app_instance.config['SECRET_KEY']
    UPLOAD_SERVICE_URL = app_instance.config['UPLOAD_SERVICE_URL']

    @app_instance.before_request
    def authenticate_request():
        """Middleware to validate JWT for protected routes."""
        # Skip authentication for health checks or public endpoints if any
        public_paths = ['/health'] # Example
        if request.path in public_paths:
            g.user = None # Indicate no authenticated user
            return

        auth_header = request.headers.get("Authorization")
        token = None
        g.user = None # Default to no user

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            # Allow access based on endpoint rules if needed, otherwise enforce auth
            # For now, assume most endpoints require auth
            if request.endpoint not in ['health_check', None]: # Allow specific endpoints if needed
                 logger.warning(f"Missing auth token for endpoint: {request.endpoint} path: {request.path}")
                 # return jsonify({"error": "Authentication token required"}), 401
                 # Let specific route handlers decide if auth is strictly required for now
                 pass # Temporarily allow request processing, handler must check g.user
            return


        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            # Store relevant user info in g for this request context
            g.user = {
                "email": payload.get("email"),
                "sub": payload.get("sub"), # Subject (usually user ID or email)
                # Add other relevant claims if needed
            }
            logger.info(f"Authenticated user: {g.user.get('email')}")
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token received.")
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            return jsonify({"error": "Invalid authentication token"}), 401
        except Exception as e:
             logger.error(f"Token decoding error: {e}", exc_info=True)
             return jsonify({"error": "Error processing token"}), 500


    @app_instance.route("/upload", methods=["POST"])
    def upload_file():
        """
        Handles file upload: authenticates, calls Upload Service, queues transcoding job.
        """
        if not g.get('user') or not g.user.get('email'):
             return jsonify({"error": "Authentication required to upload"}), 401

        user_email = g.user['email']

        # --- Validate Request ---
        if 'file' not in request.files:
            return jsonify({"error": "No file part in the request"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        output_format = request.form.get('output_format')
        if not output_format:
            return jsonify({"error": "Output format is required"}), 400

        # Secure filename and check extension (basic check)
        filename = secure_filename(file.filename)
        if not allowed_file(app_instance, filename):
             return jsonify({"error": "File type not allowed"}), 400

        logger.info(f"Upload request received for {filename} from {user_email}, format: {output_format}")

        # --- Call Upload Service ---
        upload_url = f"{UPLOAD_SERVICE_URL}/upload"
        files_data = {'file': (filename, file.stream, file.mimetype)}
        try:
            logger.debug(f"Forwarding file '{filename}' to Upload Service at {upload_url}")
            # Important: DO NOT send the user's JWT to internal services unless necessary and trusted
            upload_response = requests.post(upload_url, files=files_data, timeout=60) # Increased timeout for upload
            upload_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            upload_result = upload_response.json()
            s3_key = upload_result.get('s3_key')
            if not s3_key:
                 logger.error("Upload service did not return an s3_key.")
                 return jsonify({"error": "File upload failed internally (no key)."}), 500
            logger.info(f"File '{filename}' successfully uploaded by Upload Service, key: {s3_key}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Upload Service: {e}", exc_info=True)
            error_detail = str(e)
            try: 
                error_detail = e.response.json().get('error', str(e)) # Try to get specific error
            except Exception as e:
                logger.error(f"Error retrieving error detail: {e}")
                pass
            return jsonify({"error": f"File upload service failed: {error_detail}"}), 502 # Bad Gateway
        except Exception as e:
            logger.error(f"Unexpected error during upload service call: {e}", exc_info=True)
            return jsonify({"error": "Internal error during file upload processing"}), 500

        # --- Queue Transcoding Job ---
        try:
            # Pass the S3 key received from upload service
            job_id = add_transcoding_job(filename, s3_key, user_email, output_format)
            logger.info(f"Transcoding job queued with ID: {job_id} for file {s3_key}")

            # --- Save Job Metadata ---
            save_job_metadata(job_id, filename, output_format, user_email, status="pending")

            return jsonify({"message": "File uploaded successfully, transcoding started.", "job_id": job_id}), 202 # Accepted

        except Exception as e:
            # TODO: Consider rolling back upload or marking job as failed immediately
            logger.error(f"Failed to queue transcoding job or save metadata: {e}", exc_info=True)
            return jsonify({"error": "File uploaded, but failed to start transcoding process."}), 500


    @app_instance.route("/status/<job_id>", methods=["GET"])
    def job_status(job_id):
        """Checks the status of a Celery task."""
        if not g.get('user'):
             return jsonify({"error": "Authentication required"}), 401
        # Optional: Check if this user is allowed to see this job_id
        # job_metadata = get_job_metadata(job_id)
        # if not job_metadata or job_metadata.get('user_email') != g.user['email']:
        #     return jsonify({"error": "Job not found or access denied"}), 404

        try:
            logger.debug(f"Checking status for job ID: {job_id}")
            task_result = AsyncResult(job_id, app=g.celery_app) # Use Celery app from g

            status = task_result.status
            result_info = {
                "job_id": job_id,
                "status": status.upper(), # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
                "download_url": None,
                "error": None
            }

            if task_result.ready(): # Task finished (SUCCESS or FAILURE)
                if task_result.successful():
                    result = task_result.get() # Get the return value of the task
                    result_info["status"] = "COMPLETED" # Use consistent "COMPLETED" status
                    result_info["download_url"] = result.get("output_url") if isinstance(result, dict) else None
                    logger.info(f"Job {job_id} completed. Result: {result}")
                    # Update metadata in Redis as well upon confirmation
                    update_job_metadata(job_id, {"status": "completed", "download_url": result_info["download_url"]})
                else: # Task failed
                    result_info["status"] = "FAILED"
                    try:
                        # Celery stores exception info
                        error_info = str(task_result.info) if task_result.info else "Unknown error"
                        result_info["error"] = error_info
                        logger.error(f"Job {job_id} failed. Error: {error_info}")
                    except Exception as e:
                         logger.error(f"Error retrieving failure info for job {job_id}: {e}")
                         result_info["error"] = "Failed to retrieve error details."
                    # Update metadata in Redis
                    update_job_metadata(job_id, {"status": "failed", "error": result_info["error"]})
            else:
                 # Task is still running or pending
                 logger.debug(f"Job {job_id} status: {status}")
                 # Optionally update status in Redis if needed frequently
                 # update_job_metadata(job_id, {"status": status.lower()})


            return jsonify(result_info), 200

        except Exception as e:
            logger.error(f"Error checking status for job {job_id}: {e}", exc_info=True)
            return jsonify({"error": "Could not retrieve job status."}), 500


    @app_instance.route("/jobs", methods=["GET"])
    def get_jobs():
        """Retrieves the recent job history for the authenticated user."""
        if not g.get('user') or not g.user.get('email'):
            return jsonify({"error": "Authentication required to view job history"}), 401

        user_email = g.user['email']
        logger.info(f"Fetching job history for user: {user_email}")

        if not g.redis:
             logger.error("Redis connection not available for get_jobs.")
             return jsonify({"error": "Service temporarily unavailable"}), 503

        try:
            # Retrieve list of job IDs for the user
            user_jobs_key = f"user:{user_email}:jobs"
            # Get last 10 job IDs (adjust count as needed)
            job_ids = g.redis.lrange(user_jobs_key, 0, 9)

            job_list = []
            if job_ids:
                 # Use pipeline for efficiency if fetching many jobs
                 pipe = g.redis.pipeline()
                 for job_id in job_ids:
                     pipe.hgetall(f"job:{job_id}")
                 job_data_list = pipe.execute()

                 for job_data in job_data_list:
                     if job_data: # Check if hash exists
                         # Convert numeric strings if necessary, ensure consistency
                         job_list.append({
                             "job_id": job_data.get("job_id"),
                             "filename": job_data.get("filename"),
                             "input_format": job_data.get("input_format", "").upper(),
                             "output_format": job_data.get("output_format", "").upper(),
                             "status": job_data.get("status", "unknown").lower(),
                             "timestamp": job_data.get("timestamp"),
                             "download_url": job_data.get("download_url"), # Will be None if not set
                             "error": job_data.get("error") # Include error if present
                         })
                     else:
                          logger.warning(f"Metadata not found for job ID referenced in user list: {job_id}")


            logger.info(f"Returning {len(job_list)} jobs for user {user_email}")
            return jsonify(job_list), 200

        except Exception as e:
            logger.error(f"Error retrieving job history for {user_email}: {e}", exc_info=True)
            return jsonify({"error": "Could not retrieve job history."}), 500


    @app_instance.route("/health")
    def health_check():
        # Basic health check endpoint
        # Optionally check connections (Redis, Upload Service?)
        redis_ok = False
        if g.redis:
             try:
                 g.redis.ping()
                 redis_ok = True
             except Exception:
                  pass
        return jsonify({"status": "ok", "redis_connected": redis_ok}), 200


# --- Helper Functions ---

def allowed_file(app, filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def save_job_metadata(job_id, filename, output_format, user_email, status="pending"):
    """Saves job metadata to Redis Hash and adds ID to user's list."""
    if not g.redis:
        logger.error(f"Redis not available, cannot save metadata for job {job_id}")
        raise ConnectionError("Redis connection not available")

    job_key = f"job:{job_id}"
    user_jobs_key = f"user:{user_email}:jobs"
    input_format = filename.rsplit('.', 1)[1].upper() if '.' in filename else 'UNKNOWN'

    job_data = {
        "job_id": job_id,
        "filename": filename,
        "input_format": input_format,
        "output_format": output_format.upper(),
        "status": status,
        "user_email": user_email, # Store user email for potential checks
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "download_url": "", # Initialize as empty
        "error": "" # Initialize as empty
    }

    try:
        # Use a pipeline for atomic operations
        pipe = g.redis.pipeline()
        # Store job details in a Hash
        pipe.hset(job_key, mapping=job_data)
        # Add job ID to the beginning of the user's list
        pipe.lpush(user_jobs_key, job_id)
        # Trim the list to keep only the last N jobs (e.g., 10)
        pipe.ltrim(user_jobs_key, 0, 9)
        pipe.execute()
        logger.info(f"Saved metadata for job {job_id} for user {user_email}")
    except Exception as e:
         logger.error(f"Failed to save metadata for job {job_id}: {e}", exc_info=True)
         raise # Re-raise the exception


def update_job_metadata(job_id, updates):
    """Updates specific fields in the job metadata hash."""
    if not g.redis:
        logger.error(f"Redis not available, cannot update metadata for job {job_id}")
        return # Fail silently or raise error depending on desired behavior

    job_key = f"job:{job_id}"
    try:
        # Check if job exists before updating? Optional.
        # if not g.redis.exists(job_key):
        #    logger.warning(f"Attempted to update non-existent job: {job_key}")
        #    return

        # Use hset with mapping to update multiple fields
        g.redis.hset(job_key, mapping=updates)
        logger.info(f"Updated metadata for job {job_id} with: {updates}")
    except Exception as e:
        logger.error(f"Failed to update metadata for job {job_id}: {e}", exc_info=True)


def get_job_metadata(job_id):
    """Retrieves job metadata hash from Redis."""
    if not g.redis:
        logger.error(f"Redis not available, cannot get metadata for job {job_id}")
        return None
    job_key = f"job:{job_id}"
    try:
        return g.redis.hgetall(job_key)
    except Exception as e:
        logger.error(f"Failed to get metadata for job {job_id}: {e}", exc_info=True)
        return None

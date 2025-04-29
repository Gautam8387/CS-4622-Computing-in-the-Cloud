# ./services/upload-service/app.py
import logging
import os
import uuid

from botocore.exceptions import ClientError
# from dotenv import dotenv_values
from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

# Important: Ensure 'common' is accessible in PYTHONPATH
try:
    from common import storage
except ImportError:
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from common import storage

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

# Configuration from environment
S3_RAW_PREFIX = config.get("S3_RAW_PREFIX", "raw/")

# --- Routes ---


@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    # Could add a check to ensure S3 credentials/config seem okay via common.storage if needed
    try:
        # A simple check like listing bucket (might need permissions) or getting config
        # For now, just check if the module loaded
        if storage.S3_BUCKET_NAME:
            logger.debug(
                f"Health check: S3 bucket configured as {storage.S3_BUCKET_NAME}"
            )
            return jsonify(
                {"status": "healthy", "s3_bucket": storage.S3_BUCKET_NAME}
            ), 200
        else:
            logger.warning("Health check: S3 bucket name not configured.")
            return jsonify(
                {"status": "unhealthy", "reason": "S3 bucket name missing"}
            ), 500
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "reason": str(e)}), 500


@app.route("/upload", methods=["POST"])
def handle_upload():
    """
    Handles the file upload, saves it to S3 raw prefix, returns the S3 key.
    Expects 'media_file' in the multipart/form-data.
    """
    logger.info("Received request on /upload endpoint.")

    if "media_file" not in request.files:
        logger.warning("Upload request missing 'media_file' part.")
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["media_file"]

    if file.filename == "":
        logger.warning(
            "Upload request received with no selected file (empty filename)."
        )
        return jsonify({"error": "No selected file"}), 400

    # Sanitize filename just in case, although we use UUID for S3 key
    original_filename = secure_filename(file.filename)
    logger.info(f"Processing file: {original_filename}")

    # Generate a unique S3 key using UUID to avoid collisions
    # Keep the original extension if possible for easier identification/debugging
    file_extension = ""
    if "." in original_filename:
        file_extension = original_filename.rsplit(".", 1)[1].lower()

    # Construct S3 key: raw/<uuid>.<original_extension>
    # Ensure raw prefix ends with a slash if needed
    raw_prefix = S3_RAW_PREFIX.strip("/")
    s3_key = f"{raw_prefix}/{uuid.uuid4()}"
    if file_extension:
        s3_key += f".{file_extension}"

    logger.info(f"Generated S3 key: {s3_key}")

    try:
        # Use the common storage utility function, passing the file stream directly
        # common.storage.upload_file expects a file path, so we need a function
        # that accepts a file stream or we save temporarily (less ideal).
        # Let's modify the expectation or add a function to common.storage

        # --- Assuming common.storage.upload_fileobj exists ---
        # Example: storage.upload_fileobj(file.stream, s3_key, file.content_type)
        # OR adapt storage.upload_file to handle streams

        # -- Modification: Let's assume common.storage.upload_file can handle a stream --
        # This requires adapting the common.storage.upload_file function.
        # If common.storage.upload_file MUST take a path, we'd have to save temporarily:
        # temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{original_filename}")
        # file.save(temp_path)
        # storage.upload_file(temp_path, s3_key)
        # os.remove(temp_path)
        # But streaming directly is much better:

        logger.info(f"Uploading file stream to S3 key: {s3_key}")
        storage.upload_fileobj(
            file, s3_key, ContentType=file.mimetype
        )  # Pass file object directly
        logger.info(f"Successfully uploaded file to {s3_key}")

        # Return the generated S3 key
        return jsonify(
            {"s3_key": s3_key, "message": "File uploaded successfully"}
        ), 201  # Created

    except (
        ClientError,
        storage.S3UploadError,
        Exception,
    ) as e:  # Catch specific S3 error if defined in common
        logger.error(f"Failed to upload file to S3 ({s3_key}): {e}")
        return jsonify({"error": f"Failed to store uploaded file: {e}"}), 500


if __name__ == "__main__":
    # Use 0.0.0.0 to be accessible within Docker network
    # Port 5003 as per docker-compose example
    app.run(host="0.0.0.0", port=5003, debug=config.get("FLASK_ENV") == "development")

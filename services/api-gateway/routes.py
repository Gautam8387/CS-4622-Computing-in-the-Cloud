# ./services/api-gateway/routes.py
import datetime

import jwt
from common import add_transcoding_job
from flask import g, jsonify, request

from services.api_gateway.config import SECRET_KEY


def init_routes(app):
    @app.before_request
    def authenticate():
        token = request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token[7:]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                g.user = payload["email"]
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401
        elif request.path not in [
            "/login/google",
            "/login/github",
            "/auth/callback",
            "/",
        ]:
            return jsonify({"error": "Authentication required"}), 401

    @app.route("/upload", methods=["POST"])
    def upload_file():
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        email = request.form.get("email")
        output_format = request.form.get("output_format")
        if not file or file.filename == "" or not email or not output_format:
            return jsonify(
                {"error": "File, email, and output format are required"}
            ), 400

        job_id = add_transcoding_job(file.filename, email, output_format)
        save_job_metadata(job_id, file.filename, output_format)
        return jsonify({"job_id": job_id}), 202

    @app.route("/status/<job_id>", methods=["GET"])
    def job_status(job_id):
        # Placeholder for job status check via Celery
        from common import celery

        task_result = celery.AsyncResult(job_id)
        status = task_result.status
        if status == "SUCCESS":
            result = task_result.result
            return jsonify(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "download_url": result["output_url"],
                }
            ), 200
        return jsonify({"job_id": job_id, "status": "pending"}), 200

    @app.route("/jobs", methods=["GET"])
    def get_jobs():
        from common import redis_client

        user = g.user
        jobs_key = f"jobs:{user}"
        jobs = redis_client.lrange(jobs_key, 0, -1)
        job_list = []
        for job in jobs:
            job_data = eval(job.decode("utf-8"))  # Deserialize (simplified)
            job_list.append(
                {
                    "filename": job_data["filename"],
                    "input_format": job_data["input_format"],
                    "output_format": job_data["output_format"],
                    "status": job_data["status"],
                    "timestamp": job_data["timestamp"],
                    "download_url": job_data.get("download_url", "#"),
                }
            )
        return jsonify(job_list), 200


def allowed_file(app, filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


def save_job_metadata(job_id, filename, output_format):
    from common import redis_client

    user = g.user
    jobs_key = f"jobs:{user}"
    input_format = filename.rsplit(".", 1)[1].upper() if "." in filename else "UNKNOWN"
    job_data = {
        "job_id": job_id,
        "filename": filename,
        "input_format": input_format,
        "output_format": output_format.upper(),
        "status": "pending",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "download_url": "#",
    }
    redis_client.lpush(jobs_key, str(job_data))
    redis_client.ltrim(jobs_key, 0, 9)  # Keep last 10 jobs

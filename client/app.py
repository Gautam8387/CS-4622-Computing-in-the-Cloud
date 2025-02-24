# ./client/app.py
import os
import time
from mimetypes import guess_type

import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_pyfile("config.py")

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://accounts.google.com/o/oauth2/token",
    authorize_url="https://accounts.github.com/login/oauth/authorize",
    refresh_token_url=None,
    client_kwargs={"scope": "email profile"},
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8000/callback"),
)

github = oauth.register(
    name="github",
    client_id=os.getenv("GITHUB_CLIENT_ID"),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    refresh_token_url=None,
    client_kwargs={"scope": "user:email"},
    redirect_uri=os.getenv("REDIRECT_URI", "http://localhost:8000/callback"),
)

API_GATEWAY_URL = "http://api-gateway:5000"  # Internal Docker network name
STANDALONE_MODE = os.getenv("STANDALONE_MODE", "True") == "True"

# Supported formats
VIDEO_FORMATS = {"mp4", "avi", "mov", "mkv", "webm"}
AUDIO_FORMATS = {"mp3", "wav", "flac", "aac"}


@app.route("/")
def index():
    token = session.get("token")
    user = session.get("user")
    jobs = get_user_jobs() if token else []
    return render_template("index.html", user=user, jobs=jobs)


@app.route("/login/google")
def login_google():
    redirect_uri = url_for("callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/github")
def login_github():
    redirect_uri = url_for("callback", _external=True)
    return github.authorize_redirect(redirect_uri)


@app.route("/callback")
def callback():
    token = (
        google.authorize_access_token()
        if "google" in request.url
        else github.authorize_access_token()
    )
    session["token"] = token["access_token"]

    # Get user info
    if "google" in request.url:
        resp = google.get("https://www.googleapis.com/oauth2/v2/userinfo")
    else:
        resp = github.get("https://api.github.com/user")
    user = resp.json()
    session["user"] = {"email": user.get("email", user.get("login"))}
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("token", None)
    session.pop("user", None)
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    email = request.form.get("email")
    output_format = request.form.get("output_format")

    if not file or file.filename == "" or not email or not output_format:
        return jsonify({"error": "File, email, and output format are required"}), 400

    # Detect file type
    mime_type, _ = guess_type(file.filename)
    is_video = mime_type and mime_type.startswith("video/")
    is_audio = mime_type and mime_type.startswith("audio/")

    if not (is_video or is_audio):
        return jsonify(
            {"error": "Unsupported file type. Please upload video or audio files."}
        ), 400

    if is_video:
        if output_format not in VIDEO_FORMATS and output_format not in AUDIO_FORMATS:
            return jsonify({"error": "Invalid output format for video"}), 400
    elif is_audio:
        if output_format not in AUDIO_FORMATS:
            return jsonify({"error": "Invalid output format for audio"}), 400

    token = session.get("token")
    if not token and not STANDALONE_MODE:
        return jsonify({"error": "Authentication required"}), 401

    if STANDALONE_MODE:
        # Mock response for standalone testing
        job_id = f"mock-{int(time.time())}"
        save_mock_job(file.filename, output_format, "completed")
        return jsonify({"job_id": job_id, "status": "completed"}), 202

    # Normal behavior when integrated
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    files = {"file": (file.filename, file, file.content_type)}
    data = {"email": email, "output_format": output_format}

    try:
        response = requests.post(
            f"{API_GATEWAY_URL}/upload", files=files, data=data, headers=headers
        )
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/status/<job_id>")
def status(job_id):
    if STANDALONE_MODE:
        # Mock status response
        return jsonify({"job_id": job_id, "status": "completed"}), 200

    token = session.get("token")
    if not token:
        return jsonify({"error": "Authentication required"}), 401

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_GATEWAY_URL}/status/{job_id}", headers=headers)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500


def get_user_jobs():
    if STANDALONE_MODE:
        # Mock jobs for demo
        return [
            {
                "filename": "presentation.mov",
                "input_format": "MOV",
                "output_format": "MP4",
                "status": "completed",
                "timestamp": "2024-03-10 14:30",
                "download_url": "#",
            },
            {
                "filename": "podcast.wav",
                "input_format": "WAV",
                "output_format": "MP3",
                "status": "completed",
                "timestamp": "2024-03-10 14:15",
                "download_url": "#",
            },
            {
                "filename": "recording.mkv",
                "input_format": "MKV",
                "output_format": "MP4",
                "status": "failed",
                "timestamp": "2024-03-10 14:00",
                "download_url": "#",
            },
        ]

    # In production, fetch from API Gateway
    token = session.get("token")
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_GATEWAY_URL}/jobs", headers=headers)
        return response.json() if response.status_code == 200 else []
    except requests.RequestException:
        return []


def save_mock_job(filename, output_format, status):
    # Mock job saving for standalone mode
    pass  # No actual storage needed for demo


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=app.config["DEBUG"])

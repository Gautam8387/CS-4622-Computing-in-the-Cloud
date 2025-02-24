# ./client/config.py
import os

DEBUG = os.getenv("FLASK_DEBUG", "True") == "True"
SECRET_KEY = os.getenv("SECRET_KEY", "client-secret-key")  # Fallback key
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "google-client-id")  # Fallback key
GOOGLE_CLIENT_SECRET = os.getenv(
    "GOOGLE_CLIENT_SECRET", "google-client-secret"
)  # Fallback key
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "github-client-id")  # Fallback key
GITHUB_CLIENT_SECRET = os.getenv(
    "GITHUB_CLIENT_SECRET", "github-client-secret"
)  # Fallback key
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")

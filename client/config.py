# ./client/config.py
import os

from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

# Use FLASK_ENV for consistency (development, production)
FLASK_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = FLASK_ENV == "development"
# It's crucial to use a strong, unique secret key, especially for sessions
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-insecure-default-key")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
# The client app handles the callback from the OAuth provider
OAUTH_CALLBACK_URL = os.getenv("OAUTH_CALLBACK_URL", "http://localhost:8000/callback")
# URLs for backend services
API_GATEWAY_URL = os.getenv(
    "API_GATEWAY_URL", "http://localhost:5000"
)  # Default for standalone run
AUTH_SERVICE_URL = os.getenv(
    "AUTH_SERVICE_URL", "http://localhost:5001"
)  # Default for standalone run

# Feature flag for standalone mode (useful for frontend dev without full backend)
STANDALONE_MODE = os.getenv("STANDALONE_MODE", "False") == "True"

# Ensure critical OAuth variables are set if not in standalone mode
if not STANDALONE_MODE:
    if not all(
        [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET]
    ):
        print("Warning: OAuth Client ID/Secrets are not fully configured.")

# Supported formats (can be moved to a shared location if needed by backend too)
VIDEO_FORMATS = {"mp4", "avi", "mov", "mkv", "webm"}
AUDIO_FORMATS = {"mp3", "wav", "flac", "aac"}

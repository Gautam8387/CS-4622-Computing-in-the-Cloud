# ./services/auth-service/config.py
import os

DEBUG = os.getenv("FLASK_DEBUG", "False") == "True"
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your-google-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your-google-client-secret")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "your-github-client-id")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your-github-client-secret")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5001/auth/callback")

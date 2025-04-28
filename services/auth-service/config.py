# ./services/auth-service/config.py
import os

from dotenv import load_dotenv

load_dotenv()

FLASK_ENV = os.getenv("FLASK_ENV", "production")
DEBUG = FLASK_ENV == "development"

# CRITICAL: Use a strong, unique secret key for JWT signing.
# DO NOT use the same key as other services.
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-auth-service-secret-immediately")

# Redis URL (optional, needed for session storage or JWT blocklisting)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# OAuth Provider Credentials (Loaded from environment)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Ensure critical OAuth variables are set
if not all(
    [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET]
):
    print("Warning: Auth Service OAuth Client ID/Secrets are not fully configured.")

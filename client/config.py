# ./client/config.py

import os

# --- General Flask Settings ---
# Determine run environment (development or production)
FLASK_ENV = os.environ.get('FLASK_ENV', 'production').lower()
DEBUG = FLASK_ENV == 'development'

# --- Flask Secret Key (CRITICAL for session security) ---
# Reads the specific variable name used in docker-compose.yml for this service
SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY')

# Security check: Ensure a secret key is set, especially in production
if not SECRET_KEY:
    if DEBUG:
        print("\n" + "="*50)
        print("WARNING: CLIENT_SECRET_KEY environment variable is not set.")
        print("Using a default, INSECURE key for development purposes ONLY.")
        print("Please set CLIENT_SECRET_KEY in your .env file.")
        print("="*50 + "\n")
        SECRET_KEY = 'temporary-insecure-client-dev-key-CHANGE-ME'
    else:
        # Fail hard in production if no secret key is provided
        raise ValueError("FATAL ERROR: CLIENT_SECRET_KEY environment variable must be set in production.")

# --- Application Mode ---
# Controls whether to run in standalone/mock mode
STANDALONE_MODE = os.environ.get('STANDALONE_MODE', 'False').lower() in ('true', '1', 't', 'yes')

# --- OAuth Client Credentials ---
# These MUST be set in your .env file for OAuth login to work
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET')

# --- OAuth Callback URL ---
# The URL the OAuth provider redirects back to. Must match provider configuration.
# Using url_for in the route is often more reliable, but this can be a fallback.
OAUTH_CALLBACK_URL = os.environ.get('OAUTH_CALLBACK_URL', 'http://localhost:8000/callback')

# --- Backend Service URLs ---
# How the client backend contacts other microservices
API_GATEWAY_URL = os.environ.get('API_GATEWAY_URL', 'http://api-gateway:5000')
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth-service:5001')

# --- Media Format Definitions ---
# Central place to define supported formats
VIDEO_FORMATS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
AUDIO_FORMATS = {'mp3', 'wav', 'flac', 'aac'}

# --- Configuration Loading Feedback (for debugging) ---
# This will print in the container logs when the Flask app starts
print("\n" + "="*50)
print("Client Service Configuration Loaded")
print("="*50)
print(f"  FLASK_ENV:          {FLASK_ENV}")
print(f"  DEBUG Mode:         {DEBUG}")
print(f"  STANDALONE_MODE:    {STANDALONE_MODE}")
print(f"  Secret Key Set:     {'YES' if SECRET_KEY and SECRET_KEY != 'temporary-insecure-client-dev-key-CHANGE-ME' else 'NO (Using default or not set!)'}")
print(f"  Google Client ID:   {'Set' if GOOGLE_CLIENT_ID else 'NOT SET'}")
print(f"  Google Secret:      {'Set' if GOOGLE_CLIENT_SECRET else 'NOT SET'}")
print(f"  GitHub Client ID:   {'Set' if GITHUB_CLIENT_ID else 'NOT SET'}")
print(f"  GitHub Secret:      {'Set' if GITHUB_CLIENT_SECRET else 'NOT SET'}")
print(f"  OAuth Callback URL: {OAUTH_CALLBACK_URL}")
print(f"  API Gateway URL:    {API_GATEWAY_URL}")
print(f"  Auth Service URL:   {AUTH_SERVICE_URL}")
print("="*50 + "\n")

# Check if critical OAuth variables are missing
if not STANDALONE_MODE:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("WARNING: Google OAuth credentials (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET) are missing or incomplete in the environment. Google login will fail.")
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        print("WARNING: GitHub OAuth credentials (GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET) are missing or incomplete in the environment. GitHub login will fail.")
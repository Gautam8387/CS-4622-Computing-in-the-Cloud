import os

DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-key') # Add a secret key for fallback
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
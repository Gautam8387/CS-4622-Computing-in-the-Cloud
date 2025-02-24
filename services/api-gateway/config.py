import os

DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-key') # Change this! secret-key for fallback
S3_BUCKET = os.getenv('S3_BUCKET', 'fallback-bucket') # Change this! s3-bucket for fallback
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'https://s3.amazonaws.com')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wav', 'mp3', 'flac'}
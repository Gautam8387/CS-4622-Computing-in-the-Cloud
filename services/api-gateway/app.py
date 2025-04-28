# ./services/api-gateway/app.py
import redis
from celery import Celery
from common import setup_logger
from flask import Flask, g  # Import g for request context
from routes import init_routes  # Assuming routes.py handles Flask routes

# --- App Initialization ---
app = Flask(__name__)
logger = setup_logger()

# Load configuration
app.config.from_pyfile("config.py")
logger.info(f"API Gateway running in {app.config['FLASK_ENV']} mode.")

# --- Service Connections (Initialize once) ---

# Redis Connection Pool
try:
    redis_pool = redis.ConnectionPool(
        host=app.config["REDIS_HOST"],
        port=app.config["REDIS_PORT"],
        db=0,
        decode_responses=True,  # Decode responses to strings
    )
    # Test connection
    r = redis.Redis(connection_pool=redis_pool)
    r.ping()
    logger.info("Successfully connected to Redis.")
except redis.exceptions.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
    redis_pool = None  # Set to None if connection fails

# Celery App (for accessing results, not defining tasks here)
celery_app = Celery("api_gateway_tasks")  # Use a name, can be arbitrary
celery_app.conf.update(
    broker_url=app.config["CELERY_BROKER_URL"],
    result_backend=app.config["CELERY_RESULT_BACKEND"],
    task_ignore_result=True,  # Gateway usually just checks status
    broker_connection_retry_on_startup=True,
)
logger.info(f"Celery configured with broker: {app.config['CELERY_BROKER_URL']}")


# --- Request Context ---
@app.before_request
def before_request():
    """Set up request context, e.g., DB connections."""
    if redis_pool:
        g.redis = redis.Redis(connection_pool=redis_pool)
    else:
        g.redis = None  # Make it available but None if connection failed

    g.celery_app = celery_app


@app.teardown_request
def teardown_request(exception=None):
    """Clean up request context."""
    # Redis connections from pool are managed automatically, no need to close g.redis
    pass


# --- Initialize Routes ---
init_routes(app)  # Pass the app instance to the routes setup function


# --- Main Execution ---
if __name__ == "__main__":
    # Run on port 5000 as per docker-compose
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])

# # ./client/Dockerfile
# # Use an official Python runtime as a parent image
# FROM python:3.9-slim

# # Set environment variables to prevent caching of Python bytecode
# ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONUNBUFFERED 1

# # Set the working directory in the container
# WORKDIR /app

# # Install system dependencies that might be needed (if any)
# # RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# # Copy the requirements file into the container
# COPY requirements.txt .

# # Install any needed packages specified in requirements.txt
# # Use --no-cache-dir to reduce image size
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application code into the container
# COPY . .

# # Make port 5000 available to the world outside this container
# EXPOSE 5000

# # Define environment variable (can be overridden)
# # SECRET_KEY should be set via docker-compose env_file or Kubernetes secrets
# ENV FLASK_ENV=production

# # Command to run the application using Gunicorn (recommended for production)
# # Use environment variables for configuration where possible
# # Use 'waitress' for Windows compatibility if needed, but Gunicorn is standard on Linux
# # Start Gunicorn with multiple workers (adjust based on CPU cores)
# # Bind to 0.0.0.0 to be accessible from outside the container
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]

# # For development, you might use:
# # CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

# ./client/Dockerfile
FROM python:3.9-slim
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app

# --- Corrected COPY paths ---
COPY ./client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./client/. .
# --- End Corrections ---

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
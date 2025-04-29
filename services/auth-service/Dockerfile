# services/auth-service/Dockerfile
FROM python:3.9-slim

# Prevent Python from writing .pyc files and enable stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service-specific code
COPY services/auth-service/. .

# Expose service port
EXPOSE 5002

# Run the Flask app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "app:app"]

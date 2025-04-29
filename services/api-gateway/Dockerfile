# ./services/api-gateway/Dockerfile
FROM python:3.9-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

# --- ADD APT commands to install curl ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*
# --- End ADD ---

COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# service-specific code
COPY services/api-gateway/. .

# common utilities
COPY services/common common

EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "3", "app:app"]
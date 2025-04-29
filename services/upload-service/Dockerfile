# ./services/upload-service/Dockerfile
FROM python:3.9-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
ENV PYTHONPATH="${PYTHONPATH}:/app"

COPY services/upload-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# service-specific code
COPY services/upload-service/. .

# common utilities
COPY services/common common

EXPOSE 5003
CMD ["gunicorn", "--bind", "0.0.0.0:5003", "--workers", "2", "app:app"]

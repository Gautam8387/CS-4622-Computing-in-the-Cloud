# ./services/api-gateway/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy common utilities first
COPY common ./common

# Copy service-specific files
COPY api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api-gateway/ .

EXPOSE 5000
CMD ["python", "app.py"]
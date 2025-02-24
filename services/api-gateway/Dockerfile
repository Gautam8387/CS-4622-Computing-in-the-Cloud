FROM python:3.9-slim

WORKDIR /app

# Copy common utilities first
COPY ../common ./common

# Copy service-specific files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5000
CMD ["python", "app.py"]
# ./services/auth-service/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy common utilities first (relative to ./services context)
COPY common ./common 

# Install dependencies (relative to ./services context)
COPY auth-service/requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt

# Copy service-specific code (relative to ./services context)
COPY auth-service/ . 

# Port used by the service (internally)
EXPOSE 5001

# Run the OAuth-enabled application
CMD ["python", "auth_oauth.py"]
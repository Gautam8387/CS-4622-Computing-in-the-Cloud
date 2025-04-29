#!/bin/bash
# ./scripts/deploy_aws.sh
# Example deployment script (conceptual - adapt for your CI/CD or local use)

set -e # Exit immediately if a command exits with a non-zero status.
# set -x # Print each command before executing (for debugging)

# --- Configuration ---
AWS_REGION="us-east-1" # Change as needed
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text) # Get AWS Account ID
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
PROJECT_NAME="media-transcoder" # Should match Terraform project name/prefix
IMAGE_TAG="${GITHUB_SHA:-latest}" # Use Git commit SHA if available (in CI/CD), else 'latest'

# List of services to build and push
SERVICES=( "client" "api-gateway" "auth-service" "upload-service" "transcoding-service" "notification-service" )

# --- Functions ---
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

build_and_push() {
  local service_name=$1
  local dockerfile_path=$2
  local image_uri="${ECR_REGISTRY}/${PROJECT_NAME}-${service_name}:${IMAGE_TAG}"

  log "Building Docker image for ${service_name}..."
  docker build -t "${image_uri}" -f "${dockerfile_path}" . # Build from project root context

  log "Pushing image ${image_uri} to ECR..."
  docker push "${image_uri}"
}

# --- Main Script ---

log "Starting AWS Deployment for ${PROJECT_NAME}..."

# 1. Authenticate Docker with ECR
log "Authenticating Docker with ECR for region ${AWS_REGION}..."
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# 2. Build and Push Images for all services
log "Building and pushing service images..."
build_and_push "client" "./client/Dockerfile"
build_and_push "api-gateway" "./services/api-gateway/Dockerfile"
build_and_push "auth-service" "./services/auth-service/Dockerfile"
build_and_push "upload-service" "./services/upload-service/Dockerfile"
build_and_push "transcoding-service" "./services/transcoding-service/Dockerfile"
build_and_push "notification-service" "./services/notification-service/Dockerfile"
log "All images pushed successfully."

# 3. Apply Terraform changes (passing image URIs as variables)
log "Applying Terraform configuration..."
cd ./infrastructure/terraform

# Create tfvars dynamically (example - adapt as needed)
# It's generally better to pass vars directly if possible in CI/CD
TF_VAR_FILE="deploy.auto.tfvars.json" # Terraform automatically loads these
cat <<EOF > $TF_VAR_FILE
{
  "client_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-client:${IMAGE_TAG}",
  "api_gateway_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-api-gateway:${IMAGE_TAG}",
  "auth_service_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-auth-service:${IMAGE_TAG}",
  "upload_service_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-upload-service:${IMAGE_TAG}",
  "transcoding_service_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-transcoding-service:${IMAGE_TAG}",
  "notification_service_image_uri": "${ECR_REGISTRY}/${PROJECT_NAME}-notification-service:${IMAGE_TAG}"
}
EOF

log "Running terraform init..."
terraform init -input=false

log "Running terraform plan..."
# Assuming secrets.tfvars exists and is populated
terraform plan -var-file="secrets.tfvars" -out=tfplan -input=false

log "Running terraform apply..."
terraform apply -auto-approve tfplan

# Optional: Clean up temporary tfvars file
rm -f $TF_VAR_FILE

cd ../.. # Return to project root

log "AWS Deployment completed successfully!"

# --- Post-Deployment Steps (Manual/Informational) ---
log "--- Post-Deployment Info ---"
ALB_DNS=$(terraform -chdir=./infrastructure/terraform output -raw alb_dns_name || echo 'N/A')
log "Application Load Balancer DNS: ${ALB_DNS}"
log "Configure your domain's CNAME/Alias record to point to the ALB DNS if using a custom domain."
log "Verify services are running in the ECS console for region ${AWS_REGION}."
log "---"
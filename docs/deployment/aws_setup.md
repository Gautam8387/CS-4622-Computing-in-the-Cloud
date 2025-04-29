<!-- ./docs/deployment/aws_setup.md -->

# AWS Deployment Guide

This guide outlines the steps to deploy the Media Transcoding application to AWS using Terraform and Docker.

## Prerequisites

1. **AWS Account:** An active AWS account with appropriate permissions to create resources (IAM, VPC, S3, ECS, ECR, ElastiCache, ALB, SES, etc.).
2. **AWS CLI:** Configured with credentials (preferably via IAM roles or temporary credentials, avoid long-lived access keys).
3. **Terraform CLI:** Installed locally or in your CI/CD environment.
4. **Docker & Docker Compose:** For building images.
5. **Git:** For version control.
6. **Container Registry:** An AWS ECR repository for each service (or a single repository with different tags/paths). Pre-create these or manage via Terraform.
7. **Domain Name (Optional):** A registered domain name if you want to use a custom URL for the application, configured in Route 53.
8. **SES Verification (Optional):** If using SES for email notifications, verify the sender email address/domain in the AWS SES console for the target region.
9. **OAuth Credentials:** Update OAuth provider (Google/GitHub) configurations to include the production callback URLs (e.g., `https://yourdomain.com/callback/google`).

## Deployment Steps

1. **Clone Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-directory>
    ```

2. **Configure Terraform Secrets:**
    *   Navigate to `infrastructure/terraform`.
    *   Create a `secrets.tfvars` file (this file is gitignored). Copy the structure from `secrets.tfvars.example`.
    *   Fill in sensitive values like OAuth client secrets, JWT secrets, SMTP passwords (if using SMTP), database passwords (if any), etc.

3. **Provision Infrastructure with Terraform:**
    *   Initialize Terraform:
        ```bash
        cd infrastructure/terraform
        terraform init
        ```
    *   Plan the deployment:
        ```bash
        terraform plan -var-file="secrets.tfvars" -out=tfplan
        ```
        *Review the plan carefully.*
    *   Apply the configuration:
        ```bash
        terraform apply tfplan
        ```
        *This will create the VPC, S3 bucket, ElastiCache Redis instance, ECS cluster, IAM roles, ALB, Security Groups, and skeleton Task Definitions/Services.*
    *   Note the outputs from Terraform, especially the **ALB DNS Name** and **ECR Repository URIs** (if managed by Terraform).

4. **Build and Push Docker Images:**
    *   Log in to AWS ECR:
        ```bash
        aws ecr get-login-password --region <your-aws-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-aws-region>.amazonaws.com
        ```
    *   Build and push each service's image (replace placeholders):
        ```bash
        # Example for client service
        docker build -t <your-ecr-repo-uri>/client:latest -f ./client/Dockerfile .
        docker push <your-ecr-repo-uri>/client:latest

        # Example for api-gateway service
        docker build -t <your-ecr-repo-uri>/api-gateway:latest -f ./services/api-gateway/Dockerfile .
        docker push <your-ecr-repo-uri>/api-gateway:latest

        # ... repeat for auth-service, upload-service, transcoding-service, notification-service ...
        ```
        *(Consider using Git commit SHA or semantic versioning for tags instead of `latest`)*

5. **Update Task Definitions & Deploy Services:**
    *   **Option A (Manual/AWS CLI/Console):** Update the ECS Task Definitions created by Terraform to point to the correct ECR image URIs (including the tag) pushed in the previous step. Then, update the corresponding ECS Services to force a new deployment using the updated task definition.
    *   **Option B (Terraform - Recommended):** Modify your `infrastructure/terraform/ecs.tf` file. Pass the ECR image URIs (with tags) as variables to your task definition resources. Re-run `terraform plan` and `terraform apply`. This will automatically update the task definitions and trigger new deployments in the services.
        *   *Example variable in `variables.tf`:* `variable "client_image_uri" { type = string }`
        *   *Example usage in `ecs.tf` (task definition):* `image = var.client_image_uri`
        *   *Pass variable during apply:* `terraform apply -var="client_image_uri=<your-ecr-repo-uri>/client:latest" ...` (automate this in CI/CD).

6. **Configure DNS (Optional):**
    *   If using a custom domain, go to AWS Route 53 (or your DNS provider).
    *   Create a CNAME or Alias record pointing your desired application hostname (e.g., `app.yourdomain.com`) to the **ALB DNS Name** obtained from Terraform outputs.

7. **Verify Deployment:**
    *   Access the application via the ALB DNS Name or your custom domain.
    *   Check ECS console for running tasks.
    *   Monitor logs via CloudWatch Logs for each service.
    *   Test the full workflow: Login -> Upload -> Transcode -> Notification -> Download.

## CI/CD Pipeline (Conceptual)

A CI/CD pipeline (e.g., using GitHub Actions, Jenkins, AWS CodePipeline) would automate steps 3-5:

1. **Trigger:** On push to `main` branch (or tags).
2. **Lint/Test:** Run code linters and automated tests.
3. **Build & Push Images:** Build Docker images, tag appropriately, push to ECR.
4. **Terraform Plan:** Run `terraform plan` with image tags as variables.
5. **Approval (Optional):** Manual approval step before applying infrastructure changes.
6. **Terraform Apply:** Run `terraform apply` to update infrastructure and deploy new service versions.

## Troubleshooting

*   **Check CloudWatch Logs:** Essential for debugging runtime errors in services.
*   **ECS Task Status:** Check why tasks might fail to start (resource limits, networking, entrypoint errors, health checks).
*   **Security Groups/NACLs:** Ensure proper network connectivity between services, ALB, and ElastiCache.
*   **IAM Permissions:** Verify that ECS Task Roles have necessary permissions (S3 access, SES access, etc.).
*   **Environment Variables:** Double-check that all required environment variables are correctly passed to the containers in the Task Definitions.
<!-- ./README.md -->
# Media Transcoding Application (SaaS) - CS4622 Final Project

This project implements a cloud-native SaaS application for transcoding media files (audio/video) using a microservices architecture on AWS, based on the final project report for CS4622.

**Team:** Julius Stabs Back (Gautam Ahuja, Nistha Singh)
**Date:** April 28, 2025 (Report Date)

## Architecture Overview

The application utilizes a microservices architecture orchestrated with Docker (and optionally Kubernetes) and deployed on AWS (primarily ECS Fargate, S3, ElastiCache, ALB). It follows the design principles and refinements detailed in the final report.

-   **Client (`client`):** Flask frontend for user interaction (upload UI, OAuth initiation, status display, job history).
-   **API Gateway (`api-gateway`):** Flask service acting as the single entry point for the frontend. Handles request routing, JWT authentication validation, coordinates uploads, queues transcoding tasks via Celery, and provides endpoints for status checks and job history retrieval from Redis.
-   **Auth Service (`auth-service`):** Flask service responsible for handling OAuth callbacks (Google/GitHub), exchanging authorization codes for provider tokens, fetching user profiles, and issuing signed JWTs for internal application use.
-   **Upload Service (`upload-service`):** Simple Flask service dedicated to receiving file streams from the API Gateway and uploading them to the `raw/` prefix in the S3 bucket using the `common.storage` utility.
-   **Transcoding Service (`transcoding-service`):** Celery worker service that performs the core media transcoding using FFmpeg. It downloads files from the S3 `raw/` prefix, executes FFmpeg, uploads results to the S3 `processed/` prefix, updates job status and metadata in Redis, and triggers the notification service.
-   **Notification Service (`notification-service`):** Celery worker service responsible for sending email notifications upon successful job completion. It generates pre-signed S3 download URLs and uses SMTP (or potentially AWS SES API) to send emails.
-   **Common (`common`):** Shared Python module containing utility functions, primarily for S3 interactions (uploading, downloading, pre-signed URLs) using Boto3. Not a running service.
-   **Redis:** Used as the Celery message broker, Celery result backend, and primary store for job metadata (status, URLs, errors) and user job history lists.
-   **S3:** AWS S3 bucket used for storing original uploaded files (`raw/` prefix) and successfully transcoded files (`processed/` prefix). Lifecycle rules (defined via Terraform) manage the transition of processed files to colder storage tiers after a configured period.
-   **Docker Compose:** Used for orchestrating the services for local development.
-   **Terraform:** Used for defining and provisioning the necessary AWS infrastructure (ECS, Fargate, S3, ElastiCache, ALB, IAM, etc.) via Infrastructure-as-Code.

## Local Development Setup

1.  **Prerequisites:**
    *   Docker & Docker Compose
    *   Git
    *   An AWS Account (for S3, even if running locally, unless using a local S3 alternative like MinIO)
    *   OAuth Credentials (Google/GitHub) configured for your development environment (e.g., `http://localhost:5000` callback URLs).
2.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-directory>
    ```
3.  **Configure Environment Variables:**
    *   Copy the example `.env` file (if provided) or create a new `.env` file in the project root.
    *   Fill in **all** the required values (AWS credentials/region, S3 bucket name, OAuth client IDs/secrets, JWT secrets, Redis URL, Celery broker URL, SMTP/SES details, etc.) as defined in the `.env` section above.
    *   **IMPORTANT:** Ensure `S3_BUCKET_NAME` points to a bucket you have access to. Ensure `JWT_SECRET_KEY` and `SECRET_KEY` are strong and unique secrets.
    *   **Do not commit your `.env` file to Git.** It's included in `.gitignore`.
4.  **Build and Run Services:**
    ```bash
    docker-compose build
    docker-compose up -d # Run services in detached mode
    ```
    *   You can view logs using `docker-compose logs -f` or `docker-compose logs <service_name>`.
5.  **Access the Application:**
    *   The client UI should be accessible at `http://localhost:5000`.
    *   The API Gateway is internally mapped but exposed (for browser access from client JS) at `http://localhost:5001`.

## AWS Deployment

(Refer to `docs/deployment/aws_setup.md` and `infrastructure/terraform/` for detailed instructions - these need to be created/updated based on your specific Terraform setup).

1.  **Configure AWS Credentials:** Ensure your deployment environment (e.g., GitHub Actions runner, local machine) has secure access to AWS (e.g., via IAM roles, OIDC, or configured credentials).
2.  **Provision Infrastructure:** Use Terraform to create the required AWS resources.
    ```bash
    cd infrastructure/terraform
    terraform init
    # Create a secrets.tfvars file for sensitive variables (gitignored)
    terraform plan -var-file="secrets.tfvars"
    terraform apply -var-file="secrets.tfvars"
    ```
    *   This will typically create the VPC, Subnets, Security Groups, S3 bucket, ElastiCache Redis, ECS Cluster, Fargate Task Definitions/Services, Load Balancer, IAM Roles, etc.
3.  **Build and Push Docker Images:** Build the Docker images for each service and push them to a container registry (e.g., AWS ECR). Tag them appropriately.
    ```bash
    # Example for one service (automate this in CI/CD)
    aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-aws-account-id>.dkr.ecr.<your-region>.amazonaws.com
    docker build -t <your-ecr-repo-uri>/client:latest ./client
    docker push <your-ecr-repo-uri>/client:latest
    # Repeat for other services...
    ```
4.  **Update ECS Task Definitions:** Modify the ECS Task Definitions (managed by Terraform or updated manually/via CI/CD) to use the newly pushed image URIs from ECR.
5.  **Deploy/Update ECS Services:** Trigger a deployment update for the ECS Services (e.g., via Terraform apply, AWS CLI `update-service --force-new-deployment`, or CI/CD pipeline) to pull the new task definitions and launch new containers.
6.  **Configure DNS:** Point your application's domain name (if any) to the AWS Application Load Balancer's DNS name (obtained from Terraform outputs).

## Project Structure

```bash
.
├───.env                      # Environment variables (API Keys, AWS creds, etc.) - DO NOT COMMIT
├───.gitignore                # Specifies intentionally untracked files that Git should ignore
├───README.md                 # This file
├───client                    # Frontend Flask Application (UI, OAuth redirects)
│   │   app.py
│   │   requirements.txt
│   │   Dockerfile
│   ├───static
│   │   ├───css/style.css
│   │   └───js/app.js
│   └───templates
│       │   index.html
│       └───_base.html
├───docs                      # Project documentation (Architecture, API, Deployment)
│   ├───api
│   ├───architecture
│   └───deployment
├───infrastructure            # Infrastructure-as-Code
│   ├───kubernetes            # (Optional) Kubernetes manifests
│   └───terraform             # Terraform configuration for AWS
├───scripts                   # Utility scripts (Optional: build, deploy helpers)
├───services                  # Backend Microservices
│   ├───api-gateway           # Handles routing, auth checks, job queuing
│   │   │   app.py
│   │   │   requirements.txt
│   │   └───Dockerfile
│   ├───auth-service          # Handles OAuth callbacks, JWT generation
│   │   │   app.py
│   │   │   requirements.txt
│   │   └───Dockerfile
│   ├───common                # Shared utilities (storage, logging, etc.) - Not a service
│   │   │   __init__.py
│   │   └───storage.py
│   ├───notification-service  # Sends email notifications (Celery Worker)
│   │   │   celery_app.py
│   │   │   tasks.py
│   │   │   requirements.txt
│   │   └───Dockerfile
│   ├───transcoding-service   # Performs media transcoding (Celery Worker + FFmpeg)
│   │   │   celery_app.py
│   │   │   tasks.py
│   │   │   requirements.txt
│   │   └───Dockerfile        # Installs FFmpeg
│   └───upload-service        # Handles direct file uploads to S3
│       │   app.py
│       │   requirements.txt
│       └───Dockerfile
└───docker-compose.yml        # Local development orchestration
```

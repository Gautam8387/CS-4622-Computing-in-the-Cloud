<!-- ./infrastructure/terraform/README.md -->

# Terraform Infrastructure

This directory contains Terraform configuration files (.tf) to provision the necessary AWS infrastructure for the Media Transcoding application.

## Overview

The Terraform code defines resources such as:

* VPC, Subnets (public/private), Security Groups, NAT Gateway/Instance (optional)
* S3 Bucket (for raw/processed files, with lifecycle rules)
* ElastiCache for Redis (cluster or single node)
* ECS Cluster
* ECR Repositories (optional, can be pre-created)
* IAM Roles (Task Execution Role, Task Roles with specific permissions)
* ECS Task Definitions (for each service, using Fargate launch type)
* ECS Services (defining desired count, placement, load balancing)
* Application Load Balancer (ALB) with Listeners and Target Groups
* CloudWatch Log Groups (for container logs)
* SES Domain/Email Identity Verification (optional, if using SES API)
* Route 53 Records (optional, for custom domain)

## Structure

* `main.tf`: Provider configuration, backend configuration (e.g., S3 backend for state).
* `variables.tf`: Input variable definitions (region, instance types, image URIs, etc.).
* `outputs.tf`: Outputs generated after apply (e.g., ALB DNS name, Bucket name).
* `vpc.tf`: Network resources.
* `iam.tf`: IAM roles and policies.
* `s3.tf`: S3 bucket and configuration.
* `elasticache.tf`: Redis cluster definition.
* `ecs.tf`: ECS cluster, task definitions, services, ECR repos (optional).
* `alb.tf`: Application Load Balancer setup.
* `ses.tf`: SES configuration (optional).
* `secrets.tfvars.example`: Example structure for providing sensitive variable values. **Do not commit `secrets.tfvars`.**

## Usage

1. **Prerequisites:**
    * Install Terraform CLI.
    * Configure AWS credentials securely.
2. **Initialization:**
    ```bash
    terraform init
    ```
    *(Downloads provider plugins and configures backend)*
3. **Create Secrets File:**
    * Copy `secrets.tfvars.example` to `secrets.tfvars`.
    * Fill in required sensitive values (OAuth secrets, JWT secrets, etc.).
4. **Plan:**
    ```bash
    # Pass image URIs and other non-sensitive variables if not using tfvars
    terraform plan -var-file="secrets.tfvars" \
      -var="client_image_uri=..." \
      -var="api_gateway_image_uri=..." \
      # ... other variables ...
      -out=tfplan
    ```
    *Review the plan carefully.*
5. **Apply:**
    ```bash
    terraform apply tfplan
    ```
    *(Provisions or updates resources in AWS)*
6. **Destroy (Cleanup):**
    ```bash
    terraform destroy -var-file="secrets.tfvars" # Add other vars if needed
    ```
    *(Removes resources managed by Terraform - use with caution!)*

## Backend Configuration

It is highly recommended to configure a remote backend (like S3 with DynamoDB locking) in `main.tf` to store the Terraform state file securely and enable collaboration.

## Variables

Refer to `variables.tf` for the full list of input variables. Sensitive variables should be provided via a `.tfvars` file (ignored by Git) or environment variables (`TF_VAR_variable_name`). Non-sensitive variables like image URIs are often passed via CI/CD pipeline parameters or command-line `-var` flags.
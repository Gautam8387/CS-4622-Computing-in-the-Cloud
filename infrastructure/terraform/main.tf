# ./infrastructure/terraform/main.tf

terraform {
  required_version = ">= 1.0" # Specify minimum Terraform version

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # Specify AWS provider version constraint
    }
  }

  # --- Recommended: Remote Backend Configuration ---
  # Uncomment and configure to store state remotely (e.g., in S3)
  # Replace placeholders with your actual bucket and DynamoDB table names
  /*
  backend "s3" {
    bucket         = "your-terraform-state-bucket-name-CHANGE-ME" # Needs to exist
    key            = "media-transcoder/terraform.tfstate"
    region         = "us-east-1" # Or your chosen region
    dynamodb_table = "your-terraform-state-lock-table-CHANGE-ME" # Needs to exist
    encrypt        = true
  }
  */
}

provider "aws" {
  region = var.aws_region
  # Credentials are sourced automatically from standard locations:
  # 1. Environment variables (AWS_ACCESS_KEY_ID, etc.)
  # 2. Shared credential file (~/.aws/credentials)
  # 3. AWS config file (~/.aws/config)
  # 4. EC2 instance profile or ECS task role (Recommended for CI/CD/AWS environments)
}

# --- Locals (Optional: for defining common values/tags) ---
locals {
  project_name = "media-transcoder"
  common_tags = {
    Project     = local.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# --- Resource Definitions (Referenced from other .tf files) ---
# Example: This file mainly sets up providers and backend.
# The actual resources (VPC, S3, ECS, etc.) are defined in other files
# like vpc.tf, s3.tf, ecs.tf etc., which Terraform automatically includes.
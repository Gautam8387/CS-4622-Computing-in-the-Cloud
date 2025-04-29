# ./infrastructure/terraform/variables.tf

variable "aws_region" {
  description = "AWS region to deploy resources in."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment identifier (e.g., dev, staging, prod)."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Base name for resources."
  type        = string
  default     = "media-transcoder"
}

# --- Networking ---
variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"] # Example for 2 AZs
}

variable "private_subnet_cidrs" {
  description = "List of CIDR blocks for private subnets."
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"] # Example for 2 AZs
}

variable "availability_zones" {
  description = "List of Availability Zones to use."
  type        = list(string)
  # Example: data "aws_availability_zones" "available" {}
  # default = slice(data.aws_availability_zones.available.names, 0, 2) # Use data source
  default = ["us-east-1a", "us-east-1b"] # Hardcode or use data source
}

# --- S3 ---
variable "s3_bucket_name_override" {
  description = "(Optional) Specific name for the S3 bucket. If empty, a unique name is generated."
  type        = string
  default     = "" # Let Terraform generate name by default
}

variable "s3_archive_delay_days" {
  description = "Number of days after which processed files are transitioned to Glacier IR (or other cold storage)."
  type        = number
  default     = 2 # Corresponds to 48 hours
}

# --- Redis (ElastiCache) ---
variable "redis_node_type" {
  description = "Node type for the ElastiCache Redis instance(s)."
  type        = string
  default     = "cache.t3.micro" # Example small node type
}

variable "redis_cluster_enabled" {
  description = "Set to true to enable Redis cluster mode (more complex)."
  type        = bool
  default     = false
}

variable "redis_num_nodes" {
  description = "Number of nodes in the Redis cluster/replication group (if cluster_enabled=false, this is total nodes including primary)."
  type        = number
  default     = 1 # Single node default (no replication)
}


# --- ECS / Fargate ---
variable "ecs_cpu_limit_default" {
  description = "Default CPU units to allocate per Fargate task."
  type        = number
  default     = 256 # 0.25 vCPU
}

variable "ecs_memory_limit_default" {
  description = "Default Memory (MiB) to allocate per Fargate task."
  type        = number
  default     = 512 # 0.5 GB
}

# Define image URI variables for each service
variable "client_image_uri" {
  description = "Docker image URI for the client service (e.g., from ECR)."
  type        = string
  # default   = "placeholder/client:latest" # No default, must be provided
}
variable "api_gateway_image_uri" {
  description = "Docker image URI for the api-gateway service."
  type        = string
}
variable "auth_service_image_uri" {
  description = "Docker image URI for the auth-service."
  type        = string
}
variable "upload_service_image_uri" {
  description = "Docker image URI for the upload-service."
  type        = string
}
variable "transcoding_service_image_uri" {
  description = "Docker image URI for the transcoding-service worker."
  type        = string
}
variable "notification_service_image_uri" {
  description = "Docker image URI for the notification-service worker."
  type        = string
}

variable "service_desired_count_default" {
  description = "Default desired count for stateless ECS services."
  type        = number
  default     = 1 # Start with 1, configure auto-scaling separately
}

variable "worker_desired_count_default" {
   description = "Default desired count for Celery worker ECS services."
   type        = number
   default     = 1
 }


# --- Secrets (Mark as sensitive) ---
# These should be provided via secrets.tfvars or environment variables

variable "jwt_secret_key" {
  description = "Secret key used for signing and verifying JWTs."
  type        = string
  sensitive   = true
}

variable "flask_client_secret_key" {
   description = "Secret key used by the Flask client for session signing."
   type        = string
   sensitive   = true
 }

variable "google_client_id" {
  description = "Google OAuth Client ID."
  type        = string
  sensitive   = true # Often considered sensitive
}
variable "google_client_secret" {
  description = "Google OAuth Client Secret."
  type        = string
  sensitive   = true
}

variable "github_client_id" {
  description = "GitHub OAuth Client ID."
  type        = string
  sensitive   = true # Often considered sensitive
}
variable "github_client_secret" {
  description = "GitHub OAuth Client Secret."
  type        = string
  sensitive   = true
}

# SMTP or SES Secrets (add as needed based on notification method)
variable "smtp_password" {
   description = "Password for SMTP authentication (if using SMTP)."
   type        = string
   sensitive   = true
   default     = "" # Default to empty if not using SMTP
 }

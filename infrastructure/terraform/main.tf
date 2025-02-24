# ./infrastructure/terraform/main.tf
provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags = { Name = "transcoding-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "public-subnet" }
}

# S3 Bucket
resource "aws_s3_bucket" "transcoding_bucket" {
  bucket = "${var.project_name}-bucket"
  tags   = { Name = "Transcoding Bucket" }
}

# ElastiCache (Redis)
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis"
  engine              = "redis"
  node_type           = "cache.t2.micro"
  num_cache_nodes     = 1
  parameter_group_name = "default.redis6.x"
  port                = 6379
  subnet_group_name   = aws_elasticache_subnet_group.redis.name
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = [aws_subnet.public.id]
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

# Example ECS Service (API Gateway)
resource "aws_ecs_task_definition" "api_gateway" {
  family                   = "${var.project_name}-api-gateway"
  network_mode            = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                     = "256"
  memory                  = "512"
  execution_role_arn      = aws_iam_role.ecs_task_execution.arn
  container_definitions    = jsonencode([
    {
      name  = "api-gateway"
      image = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/api-gateway:latest"
      portMappings = [{ containerPort = 5000, hostPort = 5000 }]
      environment = [
        { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
        { name = "S3_BUCKET", value = aws_s3_bucket.transcoding_bucket.bucket }
      ]
    }
  ])
}

resource "aws_ecs_service" "api_gateway" {
  name            = "api-gateway-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api_gateway.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets         = [aws_subnet.public.id]
    security_groups = [aws_security_group.ecs.id]
    assign_public_ip = true
  }
}

# Security Group
resource "aws_security_group" "ecs" {
  vpc_id = aws_vpc.main.id
  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM Role for ECS
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Existing S3 bucket resource (unchanged)
resource "aws_s3_bucket" "transcoding_bucket" {
  bucket = "${var.project_name}-bucket"
  tags   = { Name = "Transcoding Bucket" }
}

# Add lifecycle configuration
resource "aws_s3_bucket_lifecycle_configuration" "transcoding_lifecycle" {
  bucket = aws_s3_bucket.transcoding_bucket.id
  rule {
    id      = "move-to-glacier"
    status  = "Enabled"
    filter {
      prefix = "processed/"
    }
    transition {
      days          = 2  # 48 hours
      storage_class = "GLACIER"
    }
    expiration {
      days = 30  # Delete after 30 days (optional)
    }
  }
}
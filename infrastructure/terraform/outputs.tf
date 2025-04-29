# ./infrastructure/terraform/outputs.tf

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = aws_lb.main.dns_name # Assumes ALB is named 'main' in alb.tf
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket created for media files."
  value       = aws_s3_bucket.media_bucket.id # Assumes S3 bucket is named 'media_bucket' in s3.tf
}

output "redis_endpoint_address" {
  description = "Connection endpoint address for the ElastiCache Redis cluster/node."
  # Value depends on whether cluster mode is enabled or not
  value = try(aws_elasticache_replication_group.redis[0].primary_endpoint_address, aws_elasticache_cluster.redis_single[0].cache_nodes[0].address, "N/A")
  # Assumes replication group 'redis' or single cluster 'redis_single' defined in elasticache.tf
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.main.name # Assumes ECS cluster is named 'main' in ecs.tf
}
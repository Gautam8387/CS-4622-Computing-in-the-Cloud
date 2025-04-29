<!-- ./infrastructure/kubernetes/README.md -->
# Kubernetes Deployment (Optional)

This directory contains example Kubernetes manifests for deploying the Media Transcoding application.

**Note:** This setup might be more complex than using AWS ECS Fargate and is provided as an alternative deployment target example. It assumes you have a running Kubernetes cluster (e.g., EKS, GKE, K3s, Minikube).

## Prerequisites

* `kubectl` configured to connect to your cluster.
* A running Kubernetes cluster.
* An Ingress controller (like Nginx Ingress or Traefik) installed in the cluster if you want external access via domain names.
* Persistent Volume provisioner if you want Redis data persistence.
* Docker images pushed to a registry accessible by your cluster (e.g., Docker Hub, ECR, GCR).
* Kubernetes Secrets created for sensitive data (AWS creds, OAuth secrets, JWT secrets, SMTP password).

## Structure

* `./services/`: Contains individual YAML manifests for each application component (Deployments, Services, StatefulSets for Redis).

## Deployment Steps (Conceptual)

1. **Create Namespace (Optional):**
    ```bash
    kubectl create namespace media-transcoder
    ```
2. **Create Secrets:**
    * Manually create Kubernetes `Secret` objects containing the values from your `.env` file. Example:
        ```bash
        kubectl create secret generic app-secrets --from-env-file=.env -n media-transcoder
        # Or create secrets individually for better granularity
        kubectl create secret generic aws-credentials --from-literal=AWS_ACCESS_KEY_ID=... -n media-transcoder
        kubectl create secret generic oauth-secrets --from-literal=GOOGLE_CLIENT_SECRET=... -n media-transcoder
        # ... etc.
        ```
    * Update the manifests in `./services/` to reference these secrets using `envFrom` or `valueFrom`.
3. **Update Image URIs:**
    * Edit each Deployment/StatefulSet YAML file in `./services/` to point to the correct Docker image URI (including tag) in your container registry.
4. **Deploy Redis:**
    ```bash
    kubectl apply -f ./services/redis.yaml -n media-transcoder
    ```
5. **Deploy Application Services:**
    ```bash
    kubectl apply -f ./services/auth-service.yaml -n media-transcoder
    kubectl apply -f ./services/upload-service.yaml -n media-transcoder
    kubectl apply -f ./services/api-gateway.yaml -n media-transcoder
    kubectl apply -f ./services/client.yaml -n media-transcoder
    kubectl apply -f ./services/transcoding-service.yaml -n media-transcoder # Deployment for workers
    kubectl apply -f ./services/notification-service.yaml -n media-transcoder # Deployment for workers
    ```
6. **Configure Ingress (Optional):**
    * Create an `Ingress` resource YAML file to route external traffic (e.g., `app.yourdomain.com`) to the `client` service and potentially `/api` paths to the `api-gateway` service. Apply it using `kubectl apply -f ingress.yaml -n media-transcoder`.

## Notes

* These manifests are examples and may need adjustments based on your specific cluster setup (storage classes, ingress controller annotations, resource requests/limits).
* Consider using Helm or Kustomize for more robust Kubernetes application management.
* Managing worker scaling (transcoding, notification) might involve using Kubernetes Horizontal Pod Autoscalers (HPAs) based on custom metrics (like queue length) potentially exposed via Prometheus/KEDA.
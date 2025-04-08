<!-- ./infrastructure/kubernetes/README.md -->
# Kubernetes Manifests

These manifests define the deployments and services for the SaaS Media Transcoding application.

## Usage

- **Local Testing**: Use Minikube or Kind:
  1. Start cluster: `minikube start`
  2. Apply manifests: `kubectl apply -f services/`
  3. Access API Gateway: `minikube service api-gateway`
- **Production**: Deploy to AWS EKS by updating image references to ECR and adjusting environment variables.

## Notes

- Ensure Docker images are built and tagged locally or pushed to a registry.
- Adjust `LoadBalancer` to `NodePort` for local testing if needed.

<!-- ./README.md -->
# CS-4622-Computing-in-the-Cloud

## Directory Structure

Root Level:

- `.github/workflows`: CI/CD pipeline configurations
- `docker-compose.yml`: Local development environment setup
- `package.json`: Root level dependencies and scripts

Client Directory (`/client`):

- React application structure with Flask
- Organized by features and common components

Services Directory (`/services`). Each microservice has its own:

- Source code directory
- Dockerfile for containerization
- Package configuration
- Service-specific components

Infrastructure Directory (`/infrastructure`):

- Terraform configurations for cloud resources
- Kubernetes manifests for container orchestration
- Terraform modules for reusable infrastructure components

Scripts Directory (`/scripts`):

- Utility scripts for development, building, and deployment
- Setup scripts for new developers

Documentation Directory (`/docs`):

- API documentation
- Architecture diagrams
- Deployment guides

Tree:

```bash
.
├── client
│   ├── static
│   │   ├── css
│   │   └── js
│   └── templates
├── docs
│   ├── api
│   ├── architecture
│   └── deployment
├── infrastructure
│   ├── kubernetes
│   │   └── services
│   └── terraform
├── scripts
└── services
    ├── api-gateway
    ├── auth-service
    ├── common
    ├── notification-service
    ├── transcoding-service
    └── upload-service
```

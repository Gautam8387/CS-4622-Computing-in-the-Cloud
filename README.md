<!-- ./README.md -->
# CS-4622-Computing-in-the-Cloud
## Directory Structure:
Root Level:
- `.github/workflows`: CI/CD pipeline configurations
- `docker-compose.yml`: Local development environment setup
- `package.json`: Root level dependencies and scripts

Client Directory (`/client`):
- React application structure with TypeScript
- Organized by features and common components
- Separate directories for state management

Services Directory (`/services`). Each microservice has its own:
- Source code directory
- Dockerfile for containerization
- Package configuration
- Service-specific components

Infrastructure Directory (`/infrastructure`):
- Terraform configurations for cloud resources
- Kubernetes manifests for container orchestration
- Environment-specific configurations

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
├── PROJECTS.md
├── README.md
├── client
│   ├── Dockerfile
│   ├── README.md
│   ├── bun.lockb
│   ├── components.json
│   ├── eslint.config.js
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.js
│   ├── public
│   │   └── placeholder.svg
│   ├── src
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── components
│   │   │   ├── DropZone.tsx
│   │   │   ├── FormatSelector.tsx
│   │   │   ├── TranscodingHistory.tsx
│   │   │   └── ui
│   │   │       └── ...
│   │   ├── hooks
│   │   │   └── ...
│   │   ├── index.css
│   │   ├── lib
│   │   │   └── utils.ts
│   │   ├── main.tsx
│   │   ├── pages
│   │   │   ├── Index.tsx
│   │   │   └── NotFound.tsx
│   │   └── vite-env.d.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── docker-compose.yml
├── docs
│   ├── api
│   ├── architecture
│   └── deployment
├── environment.yml
├── infrastructure
│   ├── kubernetes
│   │   ├── base
│   │   │   ├── api-gateway-deployment.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── hpa.yaml
│   │   │   ├── ingress.yaml
│   │   │   ├── namespace.yaml
│   │   │   ├── secret.yaml
│   │   │   ├── services
│   │   │   │   ├── api-gateway-service.yaml
│   │   │   │   ├── auth-service.yaml
│   │   │   │   ├── notification-service.yaml
│   │   │   │   ├── transcoding-service.yaml
│   │   │   │   └── upload-service.yaml
│   │   │   ├── services.yaml
│   │   │   └── transcoding-service-deployment.yaml
│   │   └── overlays
│   └── terraform
│       ├── environments
│       ├── modules
│       └── variables.tf
├── scripts
│   ├── build.sh
│   ├── deploy.sh
│   └── setup.sh
└── services
    ├── api-gateway
    │   ├── Dockerfile
    │   ├── package.json
    │   └── src
    │       ├── config
    │       ├── middlewares
    │       ├── routes
    │       └── server.ts
    ├── auth-service
    │   ├── Dockerfile
    │   ├── package.json
    │   └── src
    │       ├── controllers
    │       ├── middleware
    │       ├── models
    │       ├── server.ts
    │       └── services
    ├── notification-service
    │   ├── Dockerfile
    │   ├── package.json
    │   └── src
    │       ├── controllers
    │       ├── providers
    │       ├── server.ts
    │       └── templates
    ├── transcoding-service
    │   ├── Dockerfile
    │   ├── package.json
    │   └── src
    │       ├── processors
    │       ├── queue
    │       ├── server.ts
    │       ├── utils
    │       └── workers
    └── upload-service
        ├── Dockerfile
        ├── package.json
        └── src
            ├── controllers
            ├── server.ts
            ├── services
            └── utils
```
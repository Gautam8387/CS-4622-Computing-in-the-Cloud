# CS-4622-Computing-in-the-Cloud

Directory Structure:

```bash
./
├── PROJECTS.md
├── README.md
├── client
│   ├── Dockerfile
│   ├── README.md
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   ├── public
│   │   └── vite.svg
│   ├── src
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── assets
│   │   │   └── react.svg
│   │   ├── components
│   │   │   ├── common
│   │   │   ├── features
│   │   │   └── layout
│   │   ├── index.css
│   │   ├── main.tsx
│   │   ├── pages
│   │   └── vite-env.d.ts
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
├── docker-compose.yml
├── docs
│   ├── api
│   ├── architecture
│   └── deployment
├── infrastructure
│   ├── kubernetes
│   │   ├── base
│   │   └── overlays
│   └── terraform
│       ├── environments
│       ├── modules
│       └── variables.tf
├── package.json
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


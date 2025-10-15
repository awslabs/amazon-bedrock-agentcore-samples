# Multi-Container ECS Deployment

## Architecture

The ECS deployment runs **3 containers in a single Fargate task**, matching the local docker-compose setup:

```
┌─────────────────────────────────────────────────────────┐
│                    ECS Fargate Task                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  PostgreSQL  │  │   Backend    │  │   Frontend   │  │
│  │  port: 5432  │  │  port: 8080  │  │  port: 3000  │  │
│  │              │  │              │  │              │  │
│  │  Sample Data │◄─┤  Flask API   │◄─┤  React App   │  │
│  │  (EFS)       │  │  Strands SDK │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                            ▲             │
└────────────────────────────────────────────┼─────────────┘
                                             │
                                    ┌────────┴────────┐
                                    │       ALB       │
                                    │    port: 80     │
                                    └────────▲────────┘
                                             │
                                        Internet
```

## Container Details

### 1. PostgreSQL Container
- **Image**: Custom image built from `Dockerfile.postgres`
- **Base**: postgres:16-alpine
- **Includes**: 
  - create_and_load_sales_data.sql
  - sales_data_sample_utf8.csv
- **Storage**: EFS volume mounted at `/var/lib/postgresql/data`
- **Health Check**: `pg_isready -U postgres`

### 2. Backend Container
- **Image**: Built from root `Dockerfile`
- **Base**: python:3.11-slim
- **Includes**: strands_agentcore_runtime.py
- **Port**: 8080
- **Database**: Connects to `localhost:5432` (same task)
- **Health Check**: `curl http://localhost:8080/health`
- **Depends On**: postgres (HEALTHY)

### 3. Frontend Container
- **Image**: Built from `client/Dockerfile`
- **Base**: nginx:alpine (multi-stage build from node:18-alpine)
- **Port**: 3000
- **API Proxy**: nginx proxies `/api/*` to `http://localhost:8080`
- **Health Check**: `curl http://localhost:3000`
- **Depends On**: backend (HEALTHY)

## Key Features

### Container Communication
All containers run in the same task, so they communicate via `localhost`:
- Frontend (nginx) → Backend: Proxies `/api/*` to `http://localhost:8080`
- Backend → PostgreSQL: `postgresql://postgres:postgres@localhost:5432/sales_db`

### No CORS Issues
ALB routes to frontend (port 3000). Nginx in the frontend container proxies API requests to backend on `localhost:8080`. From the browser's perspective, all requests go to the same origin (ALB), eliminating CORS issues.

### Data Persistence
PostgreSQL data is stored on EFS (Elastic File System):
- Survives container restarts
- Shared across availability zones
- Automatic backups via EFS

### Startup Order
1. PostgreSQL starts first
2. Backend waits for PostgreSQL to be HEALTHY
3. Frontend waits for Backend to be HEALTHY
4. ALB routes traffic to Frontend

## Resource Allocation

**Total Task Resources**:
- CPU: 2048 (2 vCPU)
- Memory: 4096 MB (4 GB)

**Approximate per container**:
- PostgreSQL: ~512 MB
- Backend: ~2048 MB
- Frontend: ~1536 MB

## Comparison to Local Development

| Aspect | Local (docker-compose) | ECS (CloudFormation) |
|--------|----------------------|---------------------|
| **Containers** | 3 separate containers | 3 containers in 1 task |
| **Networking** | Docker bridge network | Task localhost |
| **Database Storage** | Docker volume | EFS volume |
| **Load Balancer** | None (direct access) | ALB |
| **Scaling** | Manual | ECS auto-scaling |
| **Cost** | Free (local) | ~$85-105/month |

## Benefits of This Approach

✅ **Simplicity**: Matches local development exactly
✅ **No External Dependencies**: No RDS, no S3, single deployment
✅ **Easy to Understand**: All components in one place
✅ **Cost Effective**: Single Fargate task + EFS
✅ **Quick Setup**: One CloudFormation stack
✅ **Development Parity**: Local and production are identical

## Limitations

⚠️ **Not Production-Grade**: For demo/development purposes
⚠️ **Single Point of Failure**: All containers in one task
⚠️ **Limited Scaling**: Can't scale containers independently
⚠️ **Database in Container**: Not recommended for production data
⚠️ **No High Availability**: Single task deployment

## Production Recommendations

For production workloads, consider:
1. **RDS PostgreSQL** instead of containerized database
2. **S3 + CloudFront** for frontend static hosting
3. **Separate ECS services** for backend (can scale independently)
4. **Multi-AZ deployment** for high availability
5. **Auto-scaling policies** based on CPU/memory
6. **Database backups** and disaster recovery plan

## Deployment

See [../README.md](../README.md) for detailed deployment instructions.

Quick deploy:
```bash
# Step 1: Deploy shared infrastructure
cd deployment
./deploy-infrastructure.sh

# Step 2: Deploy ECS
cd ecs
./deploy-ecs.sh
```

This will:
1. **Shared**: VPC, IAM roles, ECR, build/push 3 images
2. **ECS**: Cluster, ALB, service with 3 containers + EFS

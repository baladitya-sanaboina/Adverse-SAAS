# Development Environment

## Local SMTP inbox

Docker Compose runs Mailpit as the local SMTP server. The backend sends verification and password-reset emails to `mailpit:1025`; open `http://localhost:8025` to inspect messages and use their links. Port `1025` is also exposed so a backend running directly on the host can use `SMTP_HOST=localhost`.

Mailpit captures development mail and does not deliver it to public inboxes. Production delivery requires a trusted SMTP provider, verified sender/domain, credentials stored outside Git, and `SMTP_USE_TLS=true` where required.

## Required software

- Docker Desktop or Docker Engine with Docker Compose
- Node.js 20 and npm for optional native frontend work
- Python 3.12 for optional native backend work

## Start the complete environment

From the repository root:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Run in the background:

```bash
docker compose -f docker/docker-compose.yml up --build -d
```

View service status and logs:

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f
```

Stop the environment:

```bash
docker compose -f docker/docker-compose.yml down
```

Remove development volumes when a full local reset is required:

```bash
docker compose -f docker/docker-compose.yml down -v
```

## Startup process

1. PostgreSQL and Redis start and pass their health checks.
2. The one-shot migration service applies Prisma migrations and idempotent foundation seed data.
3. The backend starts, verifies both dependencies, and exposes `/health`.
4. Every frontend starts after the backend becomes healthy.
5. Each frontend health check verifies its own HTTP server and access to the internal backend health endpoint.

## Port mapping

| Service | URL/Port |
| --- | --- |
| PlatformOwner | http://localhost:3000 |
| Developer | http://localhost:3001 |
| CompanyAdmin | http://localhost:3002 |
| CompanyEmployee | http://localhost:3003 |
| CompanyClient | http://localhost:3004 |
| Backend | http://localhost:8000 |
| Backend health | http://localhost:8000/health |
| Swagger API documentation | http://localhost:8000/docs |
| ReDoc API documentation | http://localhost:8000/redoc |
| OpenAPI schema | http://localhost:8000/openapi.json |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## Folder overview

- `frontend/`: five independent Next.js development applications.
- `backend/`: FastAPI application and dependency connectivity checks.
- `docker/`: development Dockerfiles and Compose configuration.
- `docs/`: project and environment documentation.

## Environment configuration

Each frontend uses `.env.local`; the backend uses `.env`. Only local development values are present. The matching `.example` files are the committed templates; real production secrets do not belong in this repository.

## Foundation boundary

The backend exposes infrastructure health and tenant-context foundation endpoints. PlatformOwner displays live health, configuration, RBAC, tenant, CI, Swagger, and OpenAPI inventory information at `/dashboard/backend`. Authentication and ERP business APIs are not included yet.

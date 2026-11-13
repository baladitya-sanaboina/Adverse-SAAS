# Loopless Architecture

## Repository

```text
frontend/
├── PlatformOwner/
├── Developer/
├── CompanyAdmin/
├── CompanyEmployee/
└── CompanyClient/

backend/
docs/
docker/
.github/
```

Each frontend is an independent Next.js and TypeScript project. All five applications use one FastAPI backend. Docker Compose orchestrates the frontends, backend, PostgreSQL, Redis, and the one-shot Prisma migration service.

```text
Five Next.js applications
          ↓
      FastAPI
       ↙   ↘
PostgreSQL Redis
    ↑
Prisma migrations and seed
```

The foundation includes configuration validation, RBAC metadata, tenant context middleware, health reporting, Swagger/OpenAPI, and CI quality gates. Authentication and ERP business APIs are outside the foundation checkpoint.

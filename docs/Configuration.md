# Application Configuration

Email verification uses `EMAIL_VERIFICATION_EXPIRY_MINUTES` (default `60`) and `EMAIL_VERIFICATION_RESEND_SECONDS` (default `60`). Verification links use the role-specific origin from `CORS_ORIGINS`; SMTP settings are shared with password recovery.

Local Docker development uses Mailpit on SMTP port `1025` with `SMTP_USE_TLS=false`; its inbox UI is available at `http://localhost:8025`. External providers normally use port `587`, authentication, a verified sender, and `SMTP_USE_TLS=true`. Never commit provider credentials.

Loopless configuration is loaded from environment files. Templates are committed; local files and secrets are ignored by Git.

## Backend

Copy `backend/.env.example` to `backend/.env`. The centralized Pydantic settings service validates required values during application startup.

Configuration groups:

- Application: name, version, description, author, environment, and optional API prefix
- Infrastructure: PostgreSQL and Redis connection URLs
- Security preparation: JWT secret and expiry (authentication is not implemented on Day-8)
- Integrations: storage provider and SMTP placeholders
- Runtime: allowed CORS origins, log level, Swagger, and health-check switches

`DATABASE_URL`, `REDIS_URL`, and a JWT secret of at least 32 characters are required. Production rejects development placeholder secrets. Never commit real credentials.

## Frontend applications

Each of the five applications owns an `.env.local.example` template with:

```text
NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_APP_NAME
NEXT_PUBLIC_APP_VERSION
NEXT_PUBLIC_ENVIRONMENT
NEXT_PUBLIC_BACKEND_HEALTH_URL
BACKEND_INTERNAL_URL
```

Copy the template to `.env.local` in the relevant frontend. Public variables are validated by that application's central `lib/config.ts`. `BACKEND_INTERNAL_URL` is server-only and allows the Platform Owner proxy to use the Docker service address.

## Environments

Use `development`, `test`, `staging`, or `production`. Keep one uncommitted environment file per runtime and supply production secrets through the deployment platform.

## Health and API documentation

`GET /health` exposes only non-secret configuration metadata: load status, application version, environment, log level, storage provider, CORS origins, and feature switches. Swagger metadata uses the same centralized settings and is available at `/docs` when enabled.

## Validation workflow

```bash
cd backend
python -m unittest discover -s tests
```

Invalid required values stop startup with a clear Pydantic validation error. Restart the backend after changing its environment and rebuild a frontend after changing a `NEXT_PUBLIC_*` value.

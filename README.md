# Adverse SaaS

## Overview

Adverse is a clean multi-role SaaS starter with four frontend workspaces and one FastAPI backend. This setup now focuses on the roles the project needs most:

- `Admin`
- `Manager`
- `Employee`
- `Client`

Each role has its own Next.js application, shared auth foundations, OTP-based signup and password recovery, and a dedicated dashboard experience. The backend provides JWT authentication, PostgreSQL persistence, Redis connectivity, Prisma migrations, role-based permissions, and a health endpoint.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js + TypeScript |
| Backend | FastAPI |
| Database | PostgreSQL |
| Cache | Redis |
| Schema and migrations | Prisma |
| Production runtime | systemd, PostgreSQL, Redis, Caddy |
| Local development | Docker Compose (optional) |

## Folder Structure

```text
frontend/
├── Admin/
├── Manager/
├── Employee/
└── Client/

backend/
docs/
docker/
.github/
```

## Role Apps

| App | Port | Purpose |
| --- | ---: | --- |
| `Admin` | 3000 | Company admin workspace plus backend health page |
| `Manager` | 3001 | Team coordination, CRM, reporting, and client operations |
| `Employee` | 3002 | Day-to-day work, tasks, attendance, and documents |
| `Client` | 3003 | Project visibility, invoices, files, and tickets |

## Auth Flows

- Public signup is currently disabled for all four roles.
- Signup sends a 6-digit OTP to verify the account before first login.
- Forgot password also sends a 6-digit OTP.
- Login remains role-aware and only allows the correct workspace for the authenticated role.

## Optional Docker Development

```bash
docker compose -f docker/docker-compose.yml up --build
```

This starts all four role apps, the backend, PostgreSQL, Redis, Prisma migrations, and Mailpit.

For a VPS deployment without Docker, follow [the native deployment guide](docs/Deployment.md). CI/CD is described in [CI/CD](docs/CI-CD.md).

### Main URLs

- Admin: `http://localhost:3000`
- Manager: `http://localhost:3001`
- Employee: `http://localhost:3002`
- Client: `http://localhost:3003`
- Backend health: `http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`
- Mailpit inbox: `http://localhost:8025`

## Native Development

### Frontend

```bash
cd frontend
npm install
npm run dev --workspace @adverse/admin
```

Swap the workspace name with `@adverse/manager`, `@adverse/employee`, or `@adverse/client` as needed.

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn main:app --reload
```

## Environment Templates

- Frontend templates: `frontend/*/.env.local.example`
- Backend template: `backend/.env.example`

Use development values only and never commit real secrets.

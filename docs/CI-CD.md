# CI/CD Foundation

Loopless uses GitHub Actions to validate every push and pull request. Day-9 adds continuous integration only; it does not deploy any application.

## Workflow

The workflow is defined in `.github/workflows/ci.yml` and follows this gate sequence:

```text
Checkout → Install dependencies → Format check → Lint → Type-check → Test → Build/startup validation
```

Any failed command stops its job and marks the workflow unsuccessful. Branch protection should require the `Frontend quality and builds` and `Backend quality, tests, and startup` checks before merge.

## Frontend validation

The frontend job installs the locked workspace dependencies once and validates all five applications:

- PlatformOwner
- Developer
- CompanyAdmin
- CompanyEmployee
- CompanyClient

Prettier checks TypeScript formatting, ESLint checks code quality, TypeScript runs in strict no-emit mode, and Next.js creates a production build for every workspace.

Local commands:

```bash
cd frontend
npm ci
npm run format:check
npm run lint
npm run typecheck
npm run build
```

## Backend validation

The backend job starts isolated PostgreSQL and Redis services. It installs pinned development quality tools plus locked Prisma dependencies, checks dependency consistency, then runs:

```bash
cd backend
black --check app main.py tests
ruff check app main.py tests
mypy app main.py
python -m compileall -q main.py app tests
python -m unittest discover -s tests -v
```

CI applies the existing Prisma migrations and seed before starting FastAPI. The job requires both `/health` and `/openapi.json` to respond successfully.

## Formatting and quality standards

- Frontend formatting: Prettier
- Frontend linting: ESLint
- Frontend types: strict TypeScript
- Backend formatting: Black
- Backend linting: Ruff
- Backend types: strict mypy
- Backend tests: Python unittest

Use formatting commands locally before opening a pull request. Do not weaken a validation rule merely to make a failing change pass.

## Dependency validation

CI uses `npm ci` so package-lock files must match their manifests. Python dependencies install from `requirements-dev.txt`, and `pip check` detects incompatible packages. Critical production npm dependency audit findings fail the backend dependency step.

## Branch strategy

Create short-lived feature branches from `main`, open a pull request, and require both CI jobs before merge. Keep `main` protected and merge only reviewed, passing changes. Deployment workflows will be introduced on a later roadmap day.

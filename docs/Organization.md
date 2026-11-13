# Departments and Branches

Day-32 adds tenant-scoped organization masters for Company Admin users. It does not assign employees to departments or branches; assignments remain a later milestone.

## Data model

- A company has many departments.
- A company has many branches.
- Department names are unique inside a company, case-insensitively.
- Branch names and codes are unique inside a company, case-insensitively.
- Records are disabled with `INACTIVE` status instead of being physically deleted.

Every repository query includes the authenticated JWT `company_id`. The API does not accept or trust a company identifier from request bodies or query parameters.

## API

- `POST /company/departments`
- `GET /company/departments`
- `GET /company/departments/{id}`
- `PATCH /company/departments/{id}`
- `DELETE /company/departments/{id}`
- `POST /company/branches`
- `GET /company/branches`
- `GET /company/branches/{id}`
- `PATCH /company/branches/{id}`
- `DELETE /company/branches/{id}`

List endpoints support `search` and `status=ACTIVE|INACTIVE`. Company Admin permissions are evaluated on every request through `DEPARTMENTS` and `BRANCHES` module grants for `VIEW`, `CREATE`, `EDIT`, and `DELETE`.

## Migration and development seed

Migration `20260809150000_departments_branches` creates the tables, indexes, modules, and Company Admin permission mappings. In non-production environments, the seed adds Engineering, Human Resources, Finance, Sales, and HYD/BLR/CHE organization samples to `TEST_COMPANY` when that company exists.

Run migrations and seed through the existing Docker migration service:

```bash
docker compose -f docker/docker-compose.yml up --build migrations
```

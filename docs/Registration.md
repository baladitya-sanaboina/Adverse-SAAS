# Registration Foundation

New users created through registration are stored as `PENDING_VERIFICATION`. A role-specific verification link is generated immediately after successful creation; login becomes available only after account activation.

Day-11 implements authorized tenant and user creation only. Login, JWT access tokens, refresh tokens, sessions, and self-registration are not included.

## Creation hierarchy

```text
Platform Owner → Developer → Company → Company Admin → Employee / Client
```

| Creator | Allowed creation |
| --- | --- |
| Platform Owner | Developer |
| Developer | Company and its Company Admin |
| Company Admin | Employee and Client inside the same company |
| Employee | None |
| Client | None |

The initial Platform Owner is provisioned through controlled operations; there is no public Platform Owner self-registration endpoint.

## Endpoints

| Method | Endpoint | Required creator |
| --- | --- | --- |
| POST | `/registration/developers` | Platform Owner |
| POST | `/registration/companies` | Developer |
| POST | `/registration/company-admins` | Developer |
| POST | `/registration/employees` | Same-company Company Admin |
| POST | `/registration/clients` | Same-company Company Admin |

Until authentication is introduced, each request supplies `created_by_user_id`. The backend loads that persisted user and validates active status, role, and company scope. Day-12 replaces client-supplied creator context with authenticated token identity.

## User validation

- Name is required and contains 2–100 characters.
- Email uses validated email syntax, is normalized to lowercase, and must be globally unique.
- Password length is 12–128 characters.
- Password requires lowercase, uppercase, number, and special characters.
- `password` and `confirm_password` must match.
- Passwords are salted and hashed with scrypt before database storage.
- New users are created with `ACTIVE` status so the authorized hierarchy can continue.

Plain-text passwords and confirmation values are never returned or stored.

## Company validation

Companies are created active with a unique uppercase code. Company Admin, Employee, and Client creation requires an existing active company. Employee and Client creators must belong to that same company.

The company must have a non-empty subscription plan. Plan-specific employee/client limits are intentionally deferred until subscription limits are defined; the registration service contains the enforcement boundary for that future rule.

## Audit logging

Every successful user or company creation writes a `registration_audits` record in the same database transaction. It records:

- action (`USER_CREATED` or `COMPANY_CREATED`)
- creator
- created user, when applicable
- company
- assigned role
- timestamp

## Error handling

Registration errors use a standard response:

```json
{
  "code": "EMAIL_EXISTS",
  "detail": "Email address is already registered.",
  "errors": null
}
```

Validation failures return `422`, unauthorized hierarchy or inactive company failures return `403`, missing resources return `404`, and duplicate email/company code failures return `409`.

## Swagger and monitoring

Swagger documents all request models, response models, examples, and error responses under the `registration` group. `/health` reports registration readiness, scrypt hashing, audit logging, and endpoint count. PlatformOwner `/dashboard/backend` renders the same health information and automatically includes all registration endpoints in its API inventory.

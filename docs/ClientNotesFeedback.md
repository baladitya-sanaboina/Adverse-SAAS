# Client Notes, Feedback, and Activity

## Scope

Day-48 extends the existing Client Detail experience with three tenant-scoped sections:

- Internal notes
- Client feedback
- Client activity timeline

This is not a replacement for the platform audit log and does not introduce a separate Client Notes application.

## Data boundaries

Every record stores `company_id` and `client_id`. The company is derived from the authenticated JWT; no company, actor, or creator identifier is accepted from request payloads. Repository queries validate the parent Client against the current company before reading or writing child records.

Internal notes and the combined activity timeline are explicitly unavailable to `COMPANY_CLIENT` accounts. Feedback remains controlled by the existing `CLIENTS` permissions, allowing a future client-facing feedback flow without exposing internal notes.

## Existing permission mapping

No new module or permission was added.

| Operation | Existing permission |
| --- | --- |
| List notes | `CLIENTS.VIEW` |
| Create/update notes | `CLIENTS.EDIT` |
| Delete notes | `CLIENTS.DELETE` |
| List feedback | `CLIENTS.VIEW` |
| Create/update feedback | `CLIENTS.EDIT` |
| List activity | `CLIENTS.VIEW` |

UI controls and backend authorization use the same mapping. Backend authorization remains authoritative.

## APIs

```text
POST   /clients/{client_id}/notes
GET    /clients/{client_id}/notes
PATCH  /clients/{client_id}/notes/{note_id}
DELETE /clients/{client_id}/notes/{note_id}

POST   /clients/{client_id}/feedback
GET    /clients/{client_id}/feedback
PATCH  /clients/{client_id}/feedback/{feedback_id}

GET    /clients/{client_id}/activity
```

Notes and feedback are returned newest first using `created_at DESC, id DESC`. Activity uses the same deterministic ordering.

## Activity generation

Activity is written in the same database transaction as the successful business operation. Failed operations do not create activity.

Implemented types:

- `NOTE_ADDED`
- `NOTE_UPDATED`
- `NOTE_DELETED`
- `FEEDBACK_ADDED`
- `FEEDBACK_UPDATED`
- `CLIENT_UPDATED`
- `CONTACT_ADDED`
- `CONTACT_UPDATED`

## UI behavior

Notes, Feedback, and Activity are integrated into Client Detail. Each section has independent loading, empty, and retry states. Note deletion uses the shared confirmation dialog. The section uses the existing Poppins typography, theme tokens, shared action buttons, and responsive Client layout.

## Migration

Apply the migration through the existing Prisma workflow:

```bash
cd backend
npx prisma migrate deploy
npx prisma generate
```

Migration: `20260816180000_client_notes_feedback_activity`.

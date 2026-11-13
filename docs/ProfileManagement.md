# Profile Management

Day-19 adds authenticated self-service profile management for every Loopless role. A user can access and change only their own profile; role, company, permissions, email, and status are never accepted by the update API.

## Profile flow

1. The user signs in and opens **My Profile**.
2. `GET /profile` validates the JWT, active session, active user, and active company (for tenant users).
3. The response includes safe user, company, role, permission, personal-detail, and preference fields.
4. `PUT /profile` saves permitted personal details and preferences, records `PROFILE_UPDATED`, and returns the refreshed profile.

## Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/profile` | Read the authenticated user's profile |
| `PUT` | `/profile` | Update first/last name, phone, timezone, language, theme, and notification preference |
| `PUT` | `/profile/change-password` | Verify the current password and securely replace it |
| `POST` | `/profile/image` | Validate and upload the authenticated user's profile image |

All endpoints require a Bearer access token. The tenant is derived from the signed JWT; no client-supplied company identifier is trusted.

## Password change

The service verifies the current Argon2 password hash, requires the confirmation to match, and enforces at least 12 characters containing uppercase, lowercase, number, and symbol. The new password is hashed before storage. A successful change revokes all active sessions for that user and records `PASSWORD_CHANGED`, so the UI clears its session and returns to Login.

## Profile image upload

The upload accepts JPG, PNG, and WEBP files up to 5 MB. Both declared MIME type and file signature are validated. Files are stored under `backend/storage/profile-images` for the local-development foundation, and only the generated URL is stored on the user. A successful upload records `PROFILE_IMAGE_UPDATED`. The storage directory is excluded from Git.

## Preferences

The current foundation supports language, timezone, `system`/`light`/`dark` theme preference, and email-notification preference. Theme application itself remains a later UI concern.

## Security and audit rules

- Authentication and an active server-side session are mandatory.
- Suspended users and suspended tenant companies are rejected.
- Users cannot modify another user or change role, company, permissions, status, or email.
- Audit rows store user, company when applicable, action, and server timestamp.
- Validation and authentication failures use the standard structured API error response.

Interactive request/response schemas and validation errors are available at `/docs`; service and local-storage readiness are reported by `/health` and the Platform Owner Backend page.

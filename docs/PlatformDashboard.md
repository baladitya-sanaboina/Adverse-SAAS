# Platform Owner Dashboard

## Scope

Day-21 provides a read-only Platform Owner dashboard. It does not implement company management, subscriptions, or Developer CRUD.

## Architecture

```text
Platform Owner UI
  -> authenticated Next.js API route
  -> GET /platform/dashboard
  -> PlatformDashboardService
  -> PlatformDashboardRepository
  -> PostgreSQL + Redis + SMTP health checks
```

The endpoint requires a valid access token and the `PLATFORM_OWNER` role. It does not require `X-Company-ID` because Platform Owners operate outside a company tenant.

## Statistics flow

One aggregate database query returns total companies, Developers, employees, clients, active users, suspended companies, and unexpired active sessions. Counts are read-only and use the existing company, user, role, and session records.

## Activity flow

The recent activity query combines existing registration and authentication audit sources, orders events newest-first, and returns a bounded list. It currently exposes company/user creation, password-reset, and email-verification events that are already recorded by the application.

## Response structure

```text
statistics
recent_activities
system_health
quick_actions
```

System health reports backend, PostgreSQL, Redis, SMTP, configured storage, and API version. Quick actions are navigation metadata only.

## UI layout

The Platform Owner dashboard contains responsive statistic cards, an activity timeline, system-health rows, and quick-action links. It includes loading skeletons, an empty activity state, API error feedback, and retry behavior while preserving the existing Loopless shell, breadcrumb, Poppins typography, and light/dark palette.

## API and operations

- Swagger tag: `platform-dashboard`
- Endpoint: `GET /platform/dashboard`
- Health inventory: `platform_dashboard` in `GET /health`
- Frontend bridge: `GET /api/platform-dashboard`

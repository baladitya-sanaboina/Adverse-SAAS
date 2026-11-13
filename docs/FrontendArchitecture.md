# Frontend Architecture

## Applications

Loopless contains four independent Next.js applications. Layouts and application-shell code are intentionally owned by each application; there is no shared cross-application layout package.

| Application | Default port | Audience |
| --- | ---: | --- |
| Admin | 3000 | Company Admin |
| Manager | 3001 | Company Manager |
| Employee | 3002 | Company Employee |
| Client | 3003 | Company Client |

## Folder Structure

Each application follows the same local convention:

```text
app/                 Routes and route-group layouts
components/
  auth/              Login, signup, OTP verification, and password recovery UI
  dashboard/         Role dashboard UI and shell
  foundation/        Reusable UI, loaders, errors, and empty states
  layout/            Application-owned layout adapter
lib/                 Application navigation and auth configuration
styles/              Theme plus foundation styles
public/              Application assets
```

## Navigation

- Admin: Dashboard, Departments, Branches, Roles, Users & Invitations, Employees, Clients, Projects, Tasks, CRM, Finance, Attendance, Documents, Reports, Backend Health, Notifications, Settings, About.
- Manager: Dashboard, Team, Projects, Tasks, Clients, CRM, Attendance, Documents, Reports, Notifications, Profile, About.
- Employee: Dashboard, Projects, Tasks, Attendance, Documents, Notifications, Profile, About.
- Client: Dashboard, Projects, Invoices, Documents, Tickets, Notifications, Profile, About.

## Auth

- Every workspace has its own login and signup entry points.
- Signup sends a 6-digit OTP and routes the user to `/verify-email`.
- Forgot password sends a 6-digit OTP and routes the user to `/reset-password`.
- Workspace login only accepts the role intended for that workspace.

## Route Planning

- `/dashboard` remains the main role landing page.
- `/dashboard/backend` is available in `Admin` for backend health inspection.
- Module links such as `/employees`, `/projects`, `/crm`, `/invoices`, and `/settings` are handled by each application's local routes and shell.
- `/401`, `/403`, `/404`, and `/500` provide prepared error-state UIs.

## Responsive Behavior

- Desktop retains the collapsible sidebar and full topbar controls.
- Tablet reduces profile detail while preserving navigation and theme controls.
- Mobile uses the existing off-canvas sidebar, compact topbar, stacked foundation panels, and full-width content.

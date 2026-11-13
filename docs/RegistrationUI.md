# Registration UI

## Scope

Loopless does not provide public self-registration. `/register` redirects to `/login` in all five frontend applications.

## Authorized hierarchy

- Platform Owner creates Developer accounts from the **Developers** page.
- Developer creates a Company and its first Company Admin from the **Companies** page.
- Company Admin creates Company Employee and Company Client accounts from the **Employees** and **Clients** pages.
- Company Employee and Company Client cannot create accounts.

All registration APIs require a valid JWT access token. The backend derives the creator from the token. Employee and Client company scope is also derived from the Company Admin token; the browser cannot select or override it.

## Forms

Forms use the existing role dashboard layout, breadcrumb, grid, Poppins typography and theme. Validation is inline while fields change. Submissions expose loading, success and backend error states and prevent duplicate submits.

Each authorized management page loads its current resource list and refreshes it immediately after successful creation. Submit buttons show an animated loading spinner while disabled.

## Endpoints

| Actor | Endpoint | Result |
| --- | --- | --- |
| Platform Owner | `POST /registration/developers` | Developer |
| Developer | `POST /registration/companies` | Company |
| Developer | `POST /registration/company-admins` | Company Admin |
| Company Admin | `POST /registration/employees` | Company Employee |
| Company Admin | `POST /registration/clients` | Company Client |

`POST /registration/companies` atomically creates the Company and default Company Admin. If either insert fails, neither record is committed. Company contact email and code are unique. Authorized `GET` requests on the Developers, Companies, Employees and Clients paths provide the list views.

The frontend calls same-origin server routes. Access and refresh tokens remain in application-specific HttpOnly cookies, including automatic access-token refresh.

## Validation

- Names require at least two characters.
- Emails require a valid format.
- Passwords require at least 12 characters with uppercase, lowercase, number and symbol.
- Password confirmation must match.
- Company codes use 3–32 uppercase letters, numbers, underscores or hyphens.
- Duplicate emails and company codes display the backend error response.

Forgot Password and Email Verification are outside Day-16 scope.

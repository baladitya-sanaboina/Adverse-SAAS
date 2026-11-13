# Module Plan

## Employee Profiles (Day-41)

The Employee domain is a tenant-scoped business profile linked one-to-one to an existing authenticated User and to the existing Department, Branch, and RBAC Role. Day-41 provides the database foundation, validation, API foundation, audit records, and tenant isolation; it does not introduce a second authentication or permission system. See `EmployeeProfiles.md`.

## Company Integrations and Workflows (Day-38)

Company Admins can configure tenant-scoped Google Drive, Slack, and Stripe behavior plus basic workflow switches. This is configuration only; connectors, OAuth, webhooks, and credential storage remain deferred to their documented later phases. See `IntegrationsWorkflows.md`.

## Platform Owner

- Authentication
- Dashboard
- Developers
- Companies
- Subscriptions
- Premium Plans
- Billing
- Support
- Logs
- Settings

## Developer

- Authentication
- Permission-based Dashboard

## Company Admin

- Authentication
- Dashboard
- Departments
- Branches
- Invitations
- Users and Organization Assignments
- Role Management
- Employees
- Clients
- Projects
- Tasks
- CRM
- Finance
- Attendance
- Documents
- Reports
- Notifications
- Settings

## Company Employee

- Authentication
- Permission-based Dashboard

## Company Client

- Authentication
- Permission-based Dashboard

The Platform Owner Subscription module includes plan configuration, company assignment, feature enforcement, resource-limit enforcement, usage monitoring, warnings, upgrade recommendations, and audit history. Employee and client registration enforce their assigned limits. Project and storage validators are prepared for their future write flows. Payment gateways and billing execution remain future milestones. Other listed ERP modules remain planned unless their dedicated milestone documentation marks them implemented.

Day-35 Role Management adds tenant-owned custom roles, protected system-role visibility, reusable module/action permission selection, safe deletion, role status controls, and immediate Day-34 assignment compatibility.

Permission review and editing remain embedded in the Role create/edit workflow; no duplicate Permission Matrix page or permission system is introduced.

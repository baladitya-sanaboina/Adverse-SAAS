# Company Integrations and Workflow Settings

Day-38 establishes a tenant-scoped configuration boundary for Company Admins. It does not implement OAuth, webhooks, provider adapters, or credential storage.

## Supported configuration

- Google Drive: document upload and download switches.
- Slack: project, task, and important-alert notification switches.
- Stripe: billing workflow switch.
- Workflows: task notifications, project updates, approval flow, and client notifications.

Provider secrets, access tokens, API keys, client secrets, and webhook secrets are neither accepted nor returned by these APIs. Secure credential storage and provider connections belong to Days 83–85.

## API

| Method | Endpoint | Permission |
| --- | --- | --- |
| GET | `/company/integrations` | `SETTINGS.VIEW` |
| GET | `/company/integrations/{provider}` | `SETTINGS.VIEW` |
| PUT | `/company/integrations/{provider}` | `SETTINGS.MANAGE` |
| DELETE | `/company/integrations/{provider}` | `SETTINGS.MANAGE` |
| GET | `/company/workflow-settings` | `SETTINGS.VIEW` |
| PUT | `/company/workflow-settings` | `SETTINGS.MANAGE` |

All tenant identity comes from the authenticated JWT. The request cannot supply or override `company_id`. Repository queries always include that company identifier.

## Persistence and audit

Configuration is stored in `company_integrations` and `company_workflow_settings`. Administrative changes record `INTEGRATION_CONFIG_UPDATED`, `INTEGRATION_ENABLED`, `INTEGRATION_DISABLED`, `INTEGRATION_DISCONNECTED`, or `WORKFLOW_SETTING_UPDATED` in the existing company settings audit stream.

## UI boundary

Integrations and Workflows reuse the existing Company Settings layout. Provider configuration opens in the same content area, supports explicit loading/error/success states, and uses the shared confirmation dialog for disconnect. No native browser dropdown is introduced.

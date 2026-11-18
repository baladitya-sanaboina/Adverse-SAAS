# CI/CD

`.github/workflows/ci.yml` runs on every push and pull request. It has two required validation jobs:

- **Frontend quality and builds:** clean npm install, UI standards, formatting, lint, type checking, and production builds for all four workspaces.
- **Backend quality, tests, and startup:** pinned Python and Prisma installs, formatting, lint, type checking, compilation, database migrations and seed, unit tests, and FastAPI health checks.

The **Deploy to VPS** job runs only for a push to `main`, only after both validation jobs pass, and only when the repository variable `DEPLOY_ENABLED` is set to `true`. Pull requests and other branches never deploy.

## One-time VPS setup

The VPS runs Node.js 22, Python 3, PostgreSQL, Redis, Caddy, and five systemd services. Docker is not used. Copy a trusted checkout or release archive to the VPS for this one-time setup, then run as root:

```bash
sudo bash scripts/production/install_native.sh
```

Create `/etc/adverse/backend.env`, `/etc/adverse/frontend.env`, and `/etc/adverse/domains.env` before the first deployment. Keep those files on the VPS, owned by `root:adverse` with mode `0640`; they are not part of the repository. Use the examples in [Deployment](Deployment.md). The backend production settings require SMTP host and sender values. Caddy needs valid DNS records for all five configured hostnames before it can obtain HTTPS certificates.

The installer creates the `adverse` service/deploy account and `/opt/adverse` release directories. Add a dedicated SSH public key to `/home/adverse/.ssh/authorized_keys`; do not use the VPS root password in GitHub Actions. The account can restart only the five Adverse systemd services through a fixed root-owned wrapper.

## GitHub configuration

Add these repository secrets:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS IP address or hostname |
| `VPS_USER` | `adverse` |
| `VPS_SSH_PRIVATE_KEY` | Private half of the dedicated deploy key |
| `VPS_KNOWN_HOSTS` | Verified SSH host-key line for this host and port |

Add these repository variables:

| Variable | Value |
| --- | --- |
| `DEPLOY_ENABLED` | `true` after the VPS and env files are ready; otherwise leave unset |
| `VPS_PORT` | SSH port, if not `22` |

The action packages `github.sha` and copies it to the VPS over SSH. The VPS does not clone the repository or receive a GitHub token, so changing the repository from public to private does not require a deployment change. The deploy script builds a new release, runs Prisma migrations, switches the active symlink, restarts the services, and checks all five local HTTP endpoints. A failed health check restores the prior release.

Protect `main` with required status checks for **Frontend quality and builds** and **Backend quality, tests, and startup**. Keep `DEPLOY_ENABLED` unset while configuring the VPS; setting it to `true` turns on automatic deployment after successful CI.

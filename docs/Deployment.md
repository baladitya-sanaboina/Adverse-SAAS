# Deploying Adverse without Docker

Production runs on one Linux VPS with PostgreSQL, Redis, Caddy, FastAPI, and four Next.js apps managed by systemd. The app servers listen on localhost only; Caddy provides HTTPS using Let's Encrypt.

## Host and DNS

The native installer needs Node.js 22, Python 3 with `venv`, PostgreSQL, Redis, and Caddy. It installs the Ubuntu packages, creates the `adverse` account and release directories, installs the systemd units, and grants that account permission to restart only the Adverse services:

```bash
sudo bash scripts/production/install_native.sh
```

Point five DNS A records at the VPS:

| Host | App |
| --- | --- |
| `admin.example.com` | Admin |
| `manager.example.com` | Manager |
| `employee.example.com` | Employee |
| `client.example.com` | Client |
| `api.example.com` | FastAPI |

Allow inbound TCP 22, 80, and 443 in the VPS firewall. Caddy obtains and renews certificates for the configured names.

## One-time configuration

Create the PostgreSQL role and database with a randomly generated hexadecimal password, for example `openssl rand -hex 32`. Use that password in `DATABASE_URL` below; hexadecimal characters need no URL escaping. Keep the production files out of the repository.

```bash
sudo -u postgres psql
```

At the PostgreSQL prompt, run these commands with the generated password:

```sql
CREATE ROLE adverse LOGIN PASSWORD 'generated-password';
CREATE DATABASE adverse OWNER adverse;
\q
```

Create `/etc/adverse/backend.env` (replace every example value):

```dotenv
APP_NAME=Adverse API
APP_VERSION=0.37.0
ENVIRONMENT=production
DATABASE_URL=postgresql://adverse:URL_ENCODED_PASSWORD@127.0.0.1:5432/adverse
REDIS_URL=redis://127.0.0.1:6379/0
JWT_SECRET=GENERATE_WITH_openssl_rand_-hex_32
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-user
SMTP_PASSWORD=your-smtp-app-password
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_USE_TLS=true
CORS_ORIGINS=https://admin.example.com,https://manager.example.com,https://employee.example.com,https://client.example.com
SWAGGER_ENABLED=false
HEALTH_CHECK_ENABLED=true
PUBLIC_SIGNUP_ENABLED=false
```

Create `/etc/adverse/frontend.env` with the public URLs that match DNS:

```dotenv
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_API_URL=https://api.example.com
NEXT_PUBLIC_API_BASE_URL=https://api.example.com
NEXT_PUBLIC_BACKEND_HEALTH_URL=https://api.example.com/health
NEXT_PUBLIC_ADMIN_APP_URL=https://admin.example.com
NEXT_PUBLIC_MANAGER_APP_URL=https://manager.example.com
NEXT_PUBLIC_EMPLOYEE_APP_URL=https://employee.example.com
NEXT_PUBLIC_CLIENT_APP_URL=https://client.example.com
NEXT_PUBLIC_APP_VERSION=0.37.0
NEXT_PUBLIC_ENVIRONMENT=production
NEXT_PUBLIC_PUBLIC_SIGNUP_ENABLED=false
```

Create `/etc/adverse/domains.env` for Caddy:

```dotenv
ACME_EMAIL=ops@example.com
ADMIN_DOMAIN=admin.example.com
MANAGER_DOMAIN=manager.example.com
EMPLOYEE_DOMAIN=employee.example.com
CLIENT_DOMAIN=client.example.com
API_DOMAIN=api.example.com
```

Set file ownership and permissions, then enable Caddy after DNS points to this VPS:

```bash
sudo chown root:adverse /etc/adverse/*.env
sudo chmod 0640 /etc/adverse/*.env
sudo systemctl daemon-reload
sudo systemctl enable --now caddy
```

The backend refuses to start in production without SMTP host and sender values. Supply a working SMTP account so verification, invitations, and password recovery can send mail. After deployment, temporarily set `PUBLIC_SIGNUP_ENABLED=true` in `/etc/adverse/backend.env` to create the first company admin through the Admin app, verify the address through SMTP, then set it back to `false` and restart `adverse-backend`. Account bootstrap for a platform owner is a separate administrative operation.

## Deploys

The GitHub Actions workflow deploys only a `main` commit that passed both CI jobs. It uploads that exact commit as an archive, builds it in a new release under `/opt/adverse/releases`, applies Prisma migrations, atomically switches `/opt/adverse/current`, restarts the five services, and checks their local HTTP endpoints. If checks fail, it restores the previous release.

The first release can also be deployed manually after configuring the GitHub SSH key and repository secrets described in [CI/CD](CI-CD.md). The VPS has no GitHub token and does not clone the repository; the workflow remains compatible when the repo becomes private.

Persistent uploads live in `/opt/adverse/shared/storage` and `/opt/adverse/shared/private-storage` across releases. Back up those directories and the PostgreSQL database outside the VPS.

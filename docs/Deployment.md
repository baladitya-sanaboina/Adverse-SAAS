# Deploying Adverse to a server

This guide is for the person who sets up the production server. It runs everything on one Linux server with Docker. Caddy handles HTTPS on its own.

## What runs

| Service | What it does | Reachable from the internet |
| --- | --- | --- |
| `caddy` | HTTPS for the four app domains; gets and renews certificates | Yes: 80, 443 |
| `admin`, `manager`, `employee`, `client` | The four Next.js apps (`next build` + `next start`) | Only through Caddy |
| `backend` | FastAPI, several workers, no code reload | No (the apps call it on the internal network) |
| `migrations` | Applies Prisma migrations, then exits | No |
| `postgres`, `redis` | Data and live events; password protected | No |
| `coturn` | TURN relay so meets work on strict office/mobile networks | Yes: 3478 UDP+TCP, 49160-49200 UDP |

Files are in `docker/`:
- `docker-compose.prod.yml`
- `Caddyfile`
- `Dockerfile.backend.prod`
- `Dockerfile.web.prod`
- `.env.production.example`

## Server

- **Size:** Ubuntu 22.04/24.04 with at least 4 GB RAM and 2 CPUs (8 GB is better while building the images).
- **Docker:** Docker Engine with the compose plugin.
- **DNS:** an A record for each app domain pointing at the server, for example `admin.`, `manager.`, `team.` and `client.` under your domain.
- **Firewall:** open 80/tcp, 443/tcp, 443/udp, 3478/tcp, 3478/udp and 49160-49200/udp. Leave everything else closed.

## First deploy

1. Copy the repository to the server, for example `git clone` into `/opt/adverse`.
2. Create the four env files from their examples and fill them in. All of them are git-ignored:
   - `docker/.env.production`: domains, Postgres/Redis passwords, TURN secret and public IP. Make each secret with `openssl rand -base64 36`.
   - `backend/.env.production`:
     - `JWT_SECRET`
     - SMTP (Gmail App Password)
     - `CORS_ORIGINS`: the four `https://` domains, in the order Admin, Manager, Employee, Client
     - `TURN_URLS` pointing at your domain
   - `frontend/<App>/.env.production` for each of Admin, Manager, Employee and Client: the four app URLs. These values are built into the browser code, so never put secrets in them.
3. Build and start:

   ```bash
   cd docker
   docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
   ```

4. Check that everything is up:
   - `docker compose --env-file .env.production -f docker-compose.prod.yml ps`
   - Open each domain. The first visit can take a few seconds while Caddy gets its certificate.

The migrations run before the API starts. Development test accounts are never created in production (`ENVIRONMENT=production`).

## Updating

```bash
cd /opt/adverse && git pull
cd docker && docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

## Backups

Data lives in Docker volumes:
- `postgres_data`: the database.
- `backend_storage`: logos and profile pictures.
- `backend_private`: task files, chat and mail attachments, scripts.

A daily database dump:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U adverse adverse | gzip > /var/backups/adverse-$(date +%F).sql.gz
```

Copy the dumps and the two storage volumes off the server, for example to object storage.

## Meets (TURN)

Without TURN, meets connect directly between browsers. That works on most home networks, but often fails on office Wi-Fi and mobile data. With `TURN_URLS` (backend) and `TURN_SECRET` (compose) set:
- The API gives each signed-in person TURN credentials that last 6 hours, made with an HMAC of the shared secret.
- Nothing is stored, and the browser never sees the secret.
- coturn refuses to relay into private networks.

To also offer TURN over TLS on 443 (the strictest networks), give coturn a certificate and add `--tls-listening-port`. This is not needed for a first deploy.

## Mail

Outgoing mail uses the SMTP account in `backend/.env.production`. For Gmail:
1. Turn on 2-step verification.
2. Create an App Password.
3. Set `SMTP_USERNAME` and `SMTP_FROM_EMAIL` to the Gmail address and `SMTP_PASSWORD` to the App Password.

Gmail allows about 500 messages a day. A business mail service (Google Workspace, Amazon SES, Zoho) is better for larger volumes.

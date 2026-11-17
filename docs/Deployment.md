# Deploying Adverse to a server

This guide is for the person who sets up the production server. It runs everything on one Linux server with Docker. Caddy handles HTTPS on its own.

## What runs

| Service | What it does | Reachable from the internet |
| --- | --- | --- |
| `caddy` | HTTPS for the four app domains and the API; gets and renews certificates | Yes: 80, 443 |
| `admin`, `manager`, `employee`, `client` | The four Next.js apps (`next build` + `next start`) | Only through Caddy |
| `backend` | FastAPI, one or more workers, no code reload | Only through Caddy on the API domain |
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

- **Size:** Ubuntu 22.04/24.04 or Oracle Linux 9 with at least 4 GB RAM and 2 CPUs (8 GB is better while building the images). The compose file has tiny-VPS defaults, but four Next.js apps plus the API, Postgres and Redis still run much better with at least 4 GB.
- **Docker:** Docker Engine with the compose plugin.
- **DNS:** an A record for each app domain plus the API domain pointing at the server, for example `admin.`, `manager.`, `employee.`, `client.` and `api.` under your domain.
- **Firewall:** open 80/tcp, 443/tcp, 443/udp, 3478/tcp, 3478/udp and 49160-49200/udp. Leave everything else closed.

## First deploy

1. Copy the repository to the server, for example `git clone` into `/opt/adverse`.
2. Create the production env files from their examples and fill them in. All of them are git-ignored:
   - `docker/.env.production`: domains, Postgres/Redis passwords, TURN secret, public IP and tiny-VPS tuning values. Make each secret with `openssl rand -base64 36`.
   - `backend/.env.production`:
     - `JWT_SECRET`
     - SMTP (Gmail App Password)
     - `CORS_ORIGINS`: the four `https://` domains, in the order Admin, Manager, Employee, Client
     - `TURN_URLS` pointing at your domain
   - `frontend/<App>/.env.production` for each of Admin, Manager, Employee and Client: the four app URLs plus the public API URL. These values are built into the browser code, so never put secrets in them.
3. Build and start:

   ```bash
   cd docker
   docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
   ```

4. Check that everything is up:
   - `docker compose --env-file .env.production -f docker-compose.prod.yml ps`
   - Open each domain, plus `https://api.your-domain.example/health`. The first visit can take a few seconds while Caddy gets its certificate.

The migrations run before the API starts. Development test accounts are never created in production (`ENVIRONMENT=production`).

## Updating

Manual update:

```bash
cd /opt/adverse && git pull
cd docker && docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Git-based auto-deploy on the server:

```bash
cd /opt/adverse
sudo ./scripts/production/install_autodeploy_systemd.sh
```

This installs a systemd timer that checks `origin/main` every 2 minutes. The deploy script is change-aware:
- `frontend/` or production proxy/container changes -> full stack rebuild
- `backend/` or backend Dockerfile changes -> backend+migrations rebuild
- docs/CI-only changes -> git sync only

You can also run the detector manually:

```bash
cd /opt/adverse
./scripts/production/auto_deploy.sh
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

## Installable apps and push notifications

Each app can be installed from Chrome, Edge or Safari ("Install app" in the address bar, or the "Install Adverse as an app" card). Installed apps open in their own window.

Push notifications reach phones and computers even when the app is closed, once the person has allowed notifications. They need a VAPID key pair in `backend/.env.production`. Make one once:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python -c "
import base64; from cryptography.hazmat.primitives import serialization; from py_vapid import Vapid01
v = Vapid01(); v.generate_keys(); b = lambda x: base64.urlsafe_b64encode(x).rstrip(b'=').decode()
print('VAPID_PUBLIC_KEY=' + b(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
print('VAPID_PRIVATE_KEY=' + b(v.private_key.private_numbers().private_value.to_bytes(32, 'big')))"
```

Then:
- Put both lines in `backend/.env.production`.
- Set `VAPID_SUBJECT` to `mailto:` plus an address you read.
- Restart the backend.

Changing the keys later means everyone has to allow notifications again.

- **iPhone and iPad:** push only works after the app is added to the Home Screen (Share, then "Add to Home Screen") on iOS 16.4 or later.
- **Office networks:** push uses the browser's own push service (Google, Mozilla or Apple), so it needs internet access from the person's device. It does not need any extra ports on the server.

## Mail

Outgoing mail uses the SMTP account in `backend/.env.production`. For Gmail:
1. Turn on 2-step verification.
2. Create an App Password.
3. Set `SMTP_USERNAME` and `SMTP_FROM_EMAIL` to the Gmail address and `SMTP_PASSWORD` to the App Password.

Gmail allows about 500 messages a day. A business mail service (Google Workspace, Amazon SES, Zoho) is better for larger volumes.

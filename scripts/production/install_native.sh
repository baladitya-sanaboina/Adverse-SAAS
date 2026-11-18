#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential ca-certificates caddy curl git libpq-dev postgresql \
  nodejs npm python3 python3-dev python3-pip python3-venv redis-server sudo

node_major="$(node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || true)"
if [[ "$node_major" != "22" ]]; then
  apt-get install -y --no-install-recommends nodejs npm
  node_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
fi
if [[ "$node_major" != "22" ]]; then
  echo "Node.js 22 is required; found $(node --version)." >&2
  exit 1
fi

getent group adverse >/dev/null || groupadd --system adverse
id adverse >/dev/null 2>&1 || useradd --system --gid adverse --home-dir /home/adverse \
  --create-home --shell /bin/bash adverse
usermod -a -G adverse adverse

install -d -o adverse -g adverse -m 0750 \
  /opt/adverse /opt/adverse/incoming /opt/adverse/releases /opt/adverse/shared/storage \
  /opt/adverse/shared/private-storage
install -d -o root -g adverse -m 0750 /etc/adverse
install -d -o root -g root -m 0755 /etc/systemd/system/caddy.service.d

for unit in adverse-backend.service adverse-admin.service adverse-manager.service \
  adverse-employee.service adverse-client.service; do
  install -o root -g root -m 0644 "$repo_root/ops/systemd/$unit" "/etc/systemd/system/$unit"
done

install -o root -g root -m 0755 "$repo_root/ops/systemd/adverse-restart" /usr/local/sbin/adverse-restart
chown root:root /usr/local/sbin/adverse-restart
chmod 0755 /usr/local/sbin/adverse-restart

cat > /etc/sudoers.d/adverse-deploy <<'SUDOERS'
adverse ALL=(root) NOPASSWD: /usr/local/sbin/adverse-restart
SUDOERS
chmod 0440 /etc/sudoers.d/adverse-deploy
visudo -cf /etc/sudoers.d/adverse-deploy

install -o root -g root -m 0644 "$repo_root/docker/Caddyfile" /etc/caddy/Caddyfile
cat > /etc/systemd/system/caddy.service.d/adverse.conf <<'CADDY'
[Service]
EnvironmentFile=/etc/adverse/domains.env
CADDY

systemctl daemon-reload
systemctl enable --now postgresql.service redis-server.service
systemctl enable adverse-backend.service adverse-admin.service adverse-manager.service \
  adverse-employee.service adverse-client.service
systemctl disable --now caddy.service || true

echo "Native Adverse services are installed. Configure /etc/adverse/backend.env, frontend.env, and domains.env before deploying."

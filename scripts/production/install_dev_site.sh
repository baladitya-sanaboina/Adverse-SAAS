#!/usr/bin/env bash
# One-time setup of the dev site next to production on the same VPS (owner request 2026-11-26).
# Run as root from a checkout of this repository, after install_native.sh:
#   sudo bash scripts/production/install_dev_site.sh
# Safe to run again: existing dev env files and the dev database are kept.
#
# The dev site is a separate copy: /opt/adverse-dev, /etc/adverse-dev, database adverse_dev,
# Redis database 1, ports 8100 (API) and 3100-3103 (apps), and dev-<name> domains. The `dev`
# branch deploys here (see .github/workflows/ci.yml); `main` deploys to production.
set -Eeuo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo -E bash "$0" "$@"
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/../.." && pwd)"
prod_env=/etc/adverse
dev_env=/etc/adverse-dev

[[ -f $prod_env/backend.env && -f $prod_env/frontend.env && -f $prod_env/domains.env ]] || {
  echo "Production must be set up first (install_native.sh and /etc/adverse/*.env)." >&2
  exit 1
}

set -a; . $prod_env/domains.env; set +a
base_domain="${ADMIN_DOMAIN#*.}"
dev_host() { printf "dev-%s.%s" "$1" "$base_domain"; }

# 1. Folders
install -d -o adverse -g adverse -m 0750 \
  /opt/adverse-dev /opt/adverse-dev/incoming /opt/adverse-dev/releases \
  /opt/adverse-dev/shared/storage /opt/adverse-dev/shared/private-storage
install -d -o adverse -g adverse -m 0700 /var/backups/adverse-deploy
install -d -o root -g adverse -m 0750 $dev_env

# 2. Settings, made from production's once; never overwritten afterwards
if [[ ! -f $dev_env/backend.env ]]; then
  prod_url="$(bash -c 'set -a; . /etc/adverse/backend.env; set +a; printf "%s" "$DATABASE_URL"')"
  base="${prod_url%%\?*}"
  query=""
  [[ "$prod_url" == *\?* ]] && query="?${prod_url#*\?}"
  dev_url="${base%/*}/${base##*/}_dev$query"
  origins="https://$(dev_host admin),https://$(dev_host manager),https://$(dev_host employee),https://$(dev_host client)"
  {
    grep -vE '^(APP_NAME|ENVIRONMENT|DATABASE_URL|REDIS_URL|JWT_SECRET|MAIL_DELIVERY_ENABLED|MAIL_ALLOWED_RECIPIENTS|CORS_ORIGINS|VAPID_SUBJECT|DEFAULT_ADMIN_PASSWORD)=' \
      $prod_env/backend.env
    cat <<ENV

# Dev site (install_dev_site.sh). Mail is logged, never sent, except to the addresses in
# MAIL_ALLOWED_RECIPIENTS (the owner's own Gmail, for testing).
APP_NAME="Adverse API (dev)"
ENVIRONMENT=staging
DATABASE_URL=$dev_url
REDIS_URL=redis://127.0.0.1:6379/1
JWT_SECRET=$(openssl rand -hex 32)
MAIL_DELIVERY_ENABLED=false
MAIL_ALLOWED_RECIPIENTS=
CORS_ORIGINS=$origins
VAPID_SUBJECT=https://$(dev_host admin)
ENV
  } > $dev_env/backend.env
  sed -E \
    -e "s#https://admin\.#https://dev-admin.#g; s#https://manager\.#https://dev-manager.#g" \
    -e "s#https://employee\.#https://dev-employee.#g; s#https://client\.#https://dev-client.#g" \
    -e "s#https://api\.#https://dev-api.#g; s#127\.0\.0\.1:8000#127.0.0.1:8100#g" \
    -e "s#^NEXT_PUBLIC_ENVIRONMENT=.*#NEXT_PUBLIC_ENVIRONMENT=staging#" \
    $prod_env/frontend.env > $dev_env/frontend.env
  chown root:adverse $dev_env/backend.env $dev_env/frontend.env
  chmod 0640 $dev_env/backend.env $dev_env/frontend.env
fi

# 3. Services: the production units with dev paths and ports
declare -A port=([backend]=8100 [admin]=3100 [manager]=3101 [employee]=3102 [client]=3103)
declare -A prod_port=([backend]=8000 [admin]=3000 [manager]=3001 [employee]=3002 [client]=3003)
for name in backend admin manager employee client; do
  sed -E \
    -e "s#^(Description=.*)#\1 (dev site)#" \
    -e "s#/opt/adverse/#/opt/adverse-dev/#g; s#/etc/adverse/#/etc/adverse-dev/#g" \
    -e "s#adverse-backend\.service#adverse-dev-backend.service#g" \
    -e "s#--port ${prod_port[$name]}#--port ${port[$name]}#; s#^Environment=PORT=${prod_port[$name]}#Environment=PORT=${port[$name]}#" \
    "$repo_root/ops/systemd/adverse-$name.service" > "/etc/systemd/system/adverse-dev-$name.service"
  chmod 0644 "/etc/systemd/system/adverse-dev-$name.service"
done
cat > /usr/local/sbin/adverse-dev-restart <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
units=(adverse-dev-backend.service adverse-dev-admin.service adverse-dev-manager.service adverse-dev-employee.service adverse-dev-client.service)
/usr/bin/systemctl restart "${units[@]}"
for unit in "${units[@]}"; do
  /usr/bin/systemctl is-active --quiet "$unit"
done
SH
chmod 0755 /usr/local/sbin/adverse-dev-restart
echo "adverse ALL=(root) NOPASSWD: /usr/local/sbin/adverse-dev-restart" > /etc/sudoers.d/adverse-dev-deploy
chmod 0440 /etc/sudoers.d/adverse-dev-deploy
visudo -cf /etc/sudoers.d/adverse-dev-deploy
install -o root -g root -m 0750 "$script_dir/refresh_dev_data.sh" /usr/local/sbin/adverse-dev-refresh
systemctl daemon-reload
systemctl enable adverse-dev-backend.service adverse-dev-admin.service adverse-dev-manager.service \
  adverse-dev-employee.service adverse-dev-client.service

# 4. Database: a copy of production, made only the first time
dev_db="$(bash -c 'set -a; . /etc/adverse-dev/backend.env; set +a; u="${DATABASE_URL%%\?*}"; printf "%s" "${u##*/}"')"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$dev_db'" | grep -q 1; then
  /usr/local/sbin/adverse-dev-refresh
fi

# 5. HTTPS: dev domains through Caddy, kept out of search engines
install -d -o root -g root -m 0755 /etc/caddy/sites.d
{
  echo "# Dev site (install_dev_site.sh). Needs DNS A records for these names."
  for pair in admin:3100 manager:3101 employee:3102 client:3103 api:8100; do
    printf '\n%s {\n\timport app\n\theader X-Robots-Tag "noindex, nofollow"\n\treverse_proxy 127.0.0.1:%s\n}\n' \
      "$(dev_host "${pair%%:*}")" "${pair##*:}"
  done
} > /etc/caddy/sites.d/adverse-dev.caddy
cp -p /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$(date +%Y%m%d-%H%M%S)"
install -o root -g root -m 0644 "$repo_root/docker/Caddyfile" /etc/caddy/Caddyfile.new
if (set -a; . $prod_env/domains.env; set +a; caddy validate --adapter caddyfile --config /etc/caddy/Caddyfile.new); then
  mv /etc/caddy/Caddyfile.new /etc/caddy/Caddyfile
  systemctl reload caddy
else
  rm -f /etc/caddy/Caddyfile.new
  echo "Caddy rejected the new config; production config left unchanged." >&2
  exit 1
fi

echo "Dev site ready. Point these DNS A records at this server:"
for name in admin manager employee client api; do echo "  $(dev_host $name)"; done

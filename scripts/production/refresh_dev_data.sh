#!/usr/bin/env bash
# Replace the dev site's data with a fresh copy of production (owner request 2026-11-26).
# Installed as /usr/local/sbin/adverse-dev-refresh by install_dev_site.sh; run as root:
#   sudo adverse-dev-refresh
# Production is only read. Everything on the dev site is replaced: database and uploaded files.
# Push subscriptions and sessions are dropped from the copy so the dev site never notifies real
# phones; mail on the dev site is off (MAIL_DELIVERY_ENABLED=false).
set -Eeuo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

read_url() { # <env file> <key>
  bash -c 'set -a; . "$1"; set +a; printf "%s" "${!2}"' _ "$1" "$2"
}
prod_url="$(read_url /etc/adverse/backend.env DATABASE_URL)"
dev_url="$(read_url /etc/adverse-dev/backend.env DATABASE_URL)"
dev_redis="$(read_url /etc/adverse-dev/backend.env REDIS_URL)"
db_name() { local u="${1%%\?*}"; printf "%s" "${u##*/}"; }
db_owner() { local u="${1#*://}"; u="${u%%@*}"; printf "%s" "${u%%:*}"; }
prod_db="$(db_name "$prod_url")"
dev_db="$(db_name "$dev_url")"
owner="$(db_owner "$dev_url")"

if [[ -z "$dev_db" || "$dev_db" == "$prod_db" || "$dev_db" != *dev* ]]; then
  echo "Refusing: the dev database name '$dev_db' must differ from production '$prod_db' and contain 'dev'." >&2
  exit 1
fi

echo "Copying production database '$prod_db' to '$dev_db'..."
systemctl stop adverse-dev-backend.service 2>/dev/null || true
sudo -u postgres dropdb --if-exists "$dev_db"
sudo -u postgres createdb -O "$owner" "$dev_db"
pg_dump --no-owner --no-privileges "$prod_url" | psql --quiet -v ON_ERROR_STOP=1 "$dev_url" >/dev/null
psql --quiet -v ON_ERROR_STOP=1 "$dev_url" <<'SQL'
DELETE FROM push_subscriptions;
DELETE FROM auth_sessions;
SQL

echo "Copying uploaded files..."
for folder in storage private-storage; do
  install -d -o adverse -g adverse -m 0750 "/opt/adverse-dev/shared/$folder"
  find "/opt/adverse-dev/shared/$folder" -mindepth 1 -delete
  if [[ -d "/opt/adverse/shared/$folder" ]]; then
    cp -a "/opt/adverse/shared/$folder/." "/opt/adverse-dev/shared/$folder/"
  fi
  chown -R adverse:adverse "/opt/adverse-dev/shared/$folder"
done

redis-cli -u "$dev_redis" FLUSHDB >/dev/null 2>&1 || true

if [[ -d /opt/adverse-dev/current/backend ]]; then
  echo "Applying the dev branch's database changes to the copy..."
  sudo -u adverse bash -c 'set -a; . /etc/adverse-dev/backend.env; set +a
    cd /opt/adverse-dev/current/backend && npm run --silent prisma:migrate:deploy'
  systemctl start adverse-dev-backend.service
fi
echo "Dev data now matches production as of $(date '+%Y-%m-%d %H:%M %Z')."

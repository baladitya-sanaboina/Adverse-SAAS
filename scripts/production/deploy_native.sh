#!/usr/bin/env bash
set -Eeuo pipefail

# Usage: deploy_native.sh <commit SHA> [production|dev]
# production: /opt/adverse, /etc/adverse, ports 8000 and 3000-3003 (from the main branch).
# dev:        /opt/adverse-dev, /etc/adverse-dev, ports 8100 and 3100-3103 (from the dev branch),
#             its own database; see scripts/production/install_dev_site.sh.
sha="${1:-}"
target="${2:-production}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ || ! "$target" =~ ^(production|dev)$ ]]; then
  echo "Usage: $0 <40-character commit SHA> [production|dev]" >&2
  exit 2
fi

if [[ "$target" == "dev" ]]; then
  app_root="/opt/adverse-dev"
  env_dir="/etc/adverse-dev"
  restart_helper="/usr/local/sbin/adverse-dev-restart"
  ports=(8100 3100 3101 3102 3103)
else
  app_root="/opt/adverse"
  env_dir="/etc/adverse"
  restart_helper="/usr/local/sbin/adverse-restart"
  ports=(8000 3000 3001 3002 3003)
fi
incoming="$app_root/incoming/$sha"
release="$app_root/releases/$sha"
backup_dir="/var/backups/adverse-deploy"
previous=""
switched=0

die() {
  echo "Deployment requires $1. Run scripts/production/install_native.sh first and configure $env_dir." >&2
  exit 1
}

[[ -d "$incoming" ]] || die "the uploaded release at $incoming"
[[ -f "$env_dir/backend.env" ]] || die "$env_dir/backend.env"
[[ -f "$env_dir/frontend.env" ]] || die "$env_dir/frontend.env"
command -v python3 >/dev/null || die "Python 3"
command -v node >/dev/null || die "Node.js"
command -v npm >/dev/null || die "npm"
command -v curl >/dev/null || die "curl"

mkdir -p "$app_root/releases" "$app_root/shared/storage" "$app_root/shared/private-storage"
if [[ -L "$app_root/current" ]]; then
  previous="$(readlink -f "$app_root/current")"
fi

rm -rf "$release"
mv "$incoming" "$release"
ln -sfn "$app_root/shared/storage" "$release/backend/storage"
ln -sfn "$app_root/shared/private-storage" "$release/backend/private-storage"

set -a
# These files must contain shell-compatible KEY=value entries and be readable by the adverse user.
source "$env_dir/backend.env"
source "$env_dir/frontend.env"
set +a

cd "$release/backend"
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --disable-pip-version-check --requirement requirements.txt
npm ci --no-audit --no-fund
npm run prisma:generate

if [[ "$target" == "production" ]]; then
  # A full copy of the live database before any migration runs, so a bad release can be undone.
  # The last 10 are kept; the nightly backups in /var/backups/adverse are separate.
  command -v pg_dump >/dev/null || die "pg_dump"
  mkdir -p "$backup_dir"
  chmod 700 "$backup_dir"
  dump="$backup_dir/before-${sha:0:12}-$(date -u +%Y%m%d-%H%M%S).sql.gz"
  pg_dump --no-owner "$DATABASE_URL" | gzip > "$dump.tmp"
  mv "$dump.tmp" "$dump"
  chmod 600 "$dump"
  find "$backup_dir" -maxdepth 1 -type f -name 'before-*.sql.gz' -printf '%T@ %p\n' \
    | sort -rn | tail -n +11 | cut -d' ' -f2- | while IFS= read -r old; do
        [[ -n "$old" ]] && rm -f -- "$old"
      done
  echo "Database backed up to $dump"
fi

npm run prisma:migrate:deploy

cd "$release/frontend"
npm ci --no-audit --no-fund
npm run build

switch_release() {
  local target_release="$1"
  ln -sfn "$target_release" "$app_root/current.next"
  mv -Tf "$app_root/current.next" "$app_root/current"
  switched=1
}

restart_services() {
  sudo -n "$restart_helper"
}

wait_for_health() {
  local attempt ok port
  for attempt in $(seq 1 30); do
    ok=1
    curl --fail --silent "http://127.0.0.1:${ports[0]}/health" >/dev/null || ok=0
    for port in "${ports[@]:1}"; do
      curl --fail --silent "http://127.0.0.1:$port/" >/dev/null || ok=0
    done
    ((ok == 1)) && return 0
    sleep 2
  done
  return 1
}

rollback() {
  local status=$?
  if (( switched == 1 )); then
    echo "Release health check failed; restoring the previous release." >&2
    if [[ -n "$previous" && -d "$previous" ]]; then
      switch_release "$previous"
      restart_services || true
    fi
  fi
  exit "$status"
}
trap rollback ERR

switch_release "$release"
restart_services
wait_for_health
trap - ERR

find "$app_root/releases" -mindepth 1 -maxdepth 1 -type d ! -name "$sha" -printf '%T@ %p\n' \
  | sort -rn | tail -n +3 | cut -d' ' -f2- | while IFS= read -r old_release; do
      [[ -n "$old_release" ]] && rm -rf -- "$old_release"
    done

echo "Deployed $sha to $target and all five services passed local HTTP health checks."

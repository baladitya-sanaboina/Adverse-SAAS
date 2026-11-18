#!/usr/bin/env bash
set -Eeuo pipefail

sha="${1:-}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Usage: $0 <40-character commit SHA>" >&2
  exit 2
fi

app_root="/opt/adverse"
incoming="$app_root/incoming/$sha"
release="$app_root/releases/$sha"
previous=""
switched=0
services=(adverse-backend adverse-admin adverse-manager adverse-employee adverse-client)

die() {
  echo "Deployment requires $1. Run scripts/production/install_native.sh first and configure /etc/adverse." >&2
  exit 1
}

[[ -d "$incoming" ]] || die "the uploaded release at $incoming"
[[ -f /etc/adverse/backend.env ]] || die "/etc/adverse/backend.env"
[[ -f /etc/adverse/frontend.env ]] || die "/etc/adverse/frontend.env"
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
source /etc/adverse/backend.env
source /etc/adverse/frontend.env
set +a

cd "$release/backend"
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --disable-pip-version-check --requirement requirements.txt
npm ci --no-audit --no-fund
npm run prisma:generate
npm run prisma:migrate:deploy

cd "$release/frontend"
npm ci --no-audit --no-fund
npm run build

switch_release() {
  local target="$1"
  ln -sfn "$target" "$app_root/current.next"
  mv -Tf "$app_root/current.next" "$app_root/current"
  switched=1
}

restart_services() {
  sudo -n /usr/local/sbin/adverse-restart
}

wait_for_health() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl --fail --silent http://127.0.0.1:8000/health >/dev/null \
      && curl --fail --silent http://127.0.0.1:3000/ >/dev/null \
      && curl --fail --silent http://127.0.0.1:3001/ >/dev/null \
      && curl --fail --silent http://127.0.0.1:3002/ >/dev/null \
      && curl --fail --silent http://127.0.0.1:3003/ >/dev/null; then
      return 0
    fi
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

echo "Deployed $sha and all five services passed local HTTP health checks."

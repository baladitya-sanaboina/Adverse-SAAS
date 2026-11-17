#!/usr/bin/env bash
set -euo pipefail

repo_dir="${REPO_DIR:-/opt/adverse}"
branch="${BRANCH:-main}"
remote_name="${REMOTE_NAME:-origin}"
compose_dir="$repo_dir/docker"
compose_env="$compose_dir/.env.production"
compose_file="$compose_dir/docker-compose.prod.yml"
lock_file="${LOCK_FILE:-/tmp/adverse-auto-deploy.lock}"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

print_changed_files() {
  while IFS= read -r changed_file; do
    printf '  - %s\n' "$changed_file"
  done <<< "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "Missing required command: $1"
    exit 1
  fi
}

run_git() {
  git -c safe.directory="$repo_dir" "$@"
}

run_docker_compose() {
  if [ "$(id -u)" -eq 0 ]; then
    docker compose --env-file "$compose_env" -f "$compose_file" "$@"
  else
    sudo docker compose --env-file "$compose_env" -f "$compose_file" "$@"
  fi
}

classify_deploy_mode() {
  local changed_files="$1"
  local changed_file

  while IFS= read -r changed_file; do
    case "$changed_file" in
      frontend/*|docker/docker-compose.prod.yml|docker/Dockerfile.web.prod|docker/Caddyfile)
        printf 'full\n'
        return 0
        ;;
      backend/*|docker/Dockerfile.backend.prod|docker/Dockerfile.prisma)
        printf 'backend\n'
        return 0
        ;;
    esac
  done <<< "$changed_files"

  printf 'sync\n'
}

require_command git
require_command flock

exec 9>"$lock_file"
if ! flock -n 9; then
  log 'Another auto-deploy run is already in progress. Exiting.'
  exit 0
fi

if [ ! -d "$repo_dir/.git" ]; then
  log "Not a git checkout: $repo_dir"
  exit 1
fi

if [ ! -f "$compose_env" ] || [ ! -f "$compose_file" ]; then
  log 'Production compose files are missing.'
  exit 1
fi

cd "$repo_dir"
log "Fetching $remote_name/$branch"
run_git fetch "$remote_name" "$branch" --depth 1 >/dev/null

current_rev="$(run_git rev-parse HEAD)"
remote_rev="$(run_git rev-parse FETCH_HEAD)"

if [ "$current_rev" = "$remote_rev" ]; then
  log "Already up to date at ${current_rev:0:7}"
  exit 0
fi

changed_files="$(run_git diff --name-only "$current_rev" "$remote_rev")"
mode="$(classify_deploy_mode "$changed_files")"

log "Updating ${current_rev:0:7} -> ${remote_rev:0:7}"
log "Deploy mode: $mode"
log 'Changed files:'
print_changed_files "$changed_files"

run_git reset --hard "$remote_rev" >/dev/null

case "$mode" in
  sync)
    log 'Git sync completed. No container rebuild required.'
    ;;
  backend)
    log 'Rebuilding backend and migrations only.'
    cd "$compose_dir"
    run_docker_compose up -d --build migrations backend
    ;;
  full)
    log 'Rebuilding full production stack.'
    cd "$compose_dir"
    run_docker_compose up -d --build
    ;;
  *)
    log "Unknown deploy mode: $mode"
    exit 1
    ;;
esac

cd "$compose_dir"
run_docker_compose ps

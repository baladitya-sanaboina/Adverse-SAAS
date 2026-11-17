#!/usr/bin/env bash
set -euo pipefail

repo_dir="${REPO_DIR:-/opt/adverse}"
service_name="adverse-autodeploy"
service_path="/etc/systemd/system/${service_name}.service"
timer_path="/etc/systemd/system/${service_name}.timer"

if [ "$(id -u)" -ne 0 ]; then
  exec sudo "$0" "$@"
fi

cat > "$service_path" <<EOF
[Unit]
Description=Adverse automatic git deploy
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=${repo_dir}
ExecStart=${repo_dir}/scripts/production/auto_deploy.sh
EOF

cat > "$timer_path" <<EOF
[Unit]
Description=Run Adverse automatic git deploy every 2 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
AccuracySec=30s
Unit=${service_name}.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "${service_name}.timer"
systemctl restart "${service_name}.timer"
systemctl status "${service_name}.timer" --no-pager

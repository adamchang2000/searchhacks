#!/usr/bin/env bash
# Pull latest main, sync every package, restart this VM's enabled searchhacks-* services.
# Identical on every VM; what a VM *runs* is decided only by which units are enabled.
set -euo pipefail

# Wrapped in a function so bash parses the whole file before `git pull` can change it.
main() {
  cd "$HOME/searchhacks"
  git pull --ff-only

  # Every Python app. Everything runs with its committed dev config; there is no prod config.
  for pyproject in app/*/pyproject.toml; do
    (cd "$(dirname "$pyproject")" && uv sync)
  done

  # All JS workspaces.
  npm ci

  # Install/refresh unit files, then restart whichever ones this VM has enabled.
  sudo cp deploy/systemd/searchhacks-*.service /etc/systemd/system/
  sudo systemctl daemon-reload
  for unit in $(systemctl list-unit-files 'searchhacks-*.service' --state=enabled --no-legend | awk '{print $1}'); do
    echo "restarting $unit"
    sudo systemctl restart "$unit"
  done
}

main "$@"
exit

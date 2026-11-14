#!/usr/bin/env bash
# Pull latest main, sync every package, restart this VM's enabled searchhacks-* services.
# Identical on every VM; what a VM *runs* is decided only by which units are enabled.
set -euo pipefail

# Wrapped in a function so bash parses the whole file before `git pull` can change it.
main() {
  cd "$HOME/searchhacks"
  git pull --ff-only

  # Every Python app: deps + a SECRET_KEY env file (generated once, never committed).
  for pyproject in app/*/pyproject.toml; do
    app_dir="$(dirname "$pyproject")"
    (cd "$app_dir" && uv sync)
    if [ -d "$app_dir/config" ] && [ ! -f "$app_dir/config/.env" ]; then
      printf 'SECRET_KEY=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" > "$app_dir/config/.env"
    fi
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

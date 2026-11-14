#!/usr/bin/env bash
# One-time, idempotent setup for any searchhacks VM. Identical on every VM.
# Run from your laptop:  ssh <vm> 'bash -s' < deploy/bootstrap.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/adamchang2000/searchhacks}"
REPO_DIR="$HOME/searchhacks"

if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "$REPO_URL" "$REPO_DIR"
fi

exec "$REPO_DIR/deploy/update.sh"

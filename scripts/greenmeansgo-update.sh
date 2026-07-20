#!/bin/bash
# Install on the server as /usr/local/bin/greenmeansgo-update.sh (owned root, mode 755).
# Safe to invoke via `sudo /usr/local/bin/greenmeansgo-update.sh`.
set -euo pipefail

# Prefer the deploy user's cargo/home even when this script is invoked via sudo.
APP_USER="${SUDO_USER:-ubuntu}"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
APP_HOME="${APP_HOME:-/home/ubuntu}"
if [[ -f "$APP_HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$APP_HOME/.cargo/env"
elif [[ -f "$HOME/.cargo/env" ]]; then
  # shellcheck disable=SC1090
  source "$HOME/.cargo/env"
else
  echo "ERROR: cargo env not found for $APP_USER ($APP_HOME/.cargo/env)" >&2
  exit 1
fi

echo "Updating Green Means Go (as effective cargo user: $APP_USER)..."

cd /var/www/green_means_go
# data/ is gitignored — pull never replaces LCA or app DBs. Do not rm -rf data/.
# Drop any leftover local edits that would block pull (stashes preserved for audit).
if ! git diff --quiet || ! git diff --cached --quiet; then
  git stash push -m "auto-stash-before-update-$(date -u +%Y%m%dT%H%M%SZ)" || true
fi
git fetch origin main
git reset --hard origin/main

# Rebuild Rust backend
echo "Building Rust backend..."
cd african_lca_backend
cargo build --release

# Update Python dependencies
echo "Updating FastAPI dependencies..."
cd ../app
# shellcheck disable=SC1091
source venv/bin/activate
pip install -r ../requirements.txt

# Rebuild frontend
echo "Rebuilding frontend..."
cd ../african-lca-frontend
npm ci
npm run build

# Restart services
echo "Restarting services..."
supervisorctl restart all
systemctl reload nginx

echo "Update complete (data/canonical and data/app left untouched)."

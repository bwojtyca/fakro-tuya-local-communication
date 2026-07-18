#!/usr/bin/env bash
#
# Deploy the Fakro-Tuya bridge from a Mac to the LXC container on Proxmox.
#
# What it does:
#   1. Sends the code (tar over SSH) to the application dir on the container.
#   2. Uploads the local .env file (secrets) separately, without keeping it in the repo.
#   3. Ensures a Python environment (venv) and installs dependencies.
#   4. Installs/updates the systemd units and restarts the service.
#
# Configuration comes from the .env file (FAKRO_DEPLOY_* keys) and can be
# overridden with environment variables of the same names:
#   FAKRO_DEPLOY_HOST   SSH host of the container       (e.g. root@192.168.x.x)
#   FAKRO_DEPLOY_DIR    application dir on the container (/opt/fakro-bridge)
#   FAKRO_VENV_DIR      virtual environment dir          (/opt/tuya-env)
#
# Usage:
#   ./deploy/deploy.sh              # deploy + restart the service
#   ./deploy/deploy.sh --discovery  # also publish MQTT Discovery to HA

set -euo pipefail

# Repo root (one level above this script)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Read a single key from .env WITHOUT sourcing the file.
# (we don't use `. .env`, because values like LOCAL_KEY contain special
#  characters — backtick etc. — that break the bash parser)
read_env() {
    [ -f "$REPO_DIR/.env" ] || return 0
    grep -E "^$1=" "$REPO_DIR/.env" | tail -n1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

# Priority: environment variable > value from .env > default value
DEPLOY_HOST="${FAKRO_DEPLOY_HOST:-$(read_env FAKRO_DEPLOY_HOST)}"
APP_DIR="${FAKRO_DEPLOY_DIR:-$(read_env FAKRO_DEPLOY_DIR)}"
VENV_DIR="${FAKRO_VENV_DIR:-$(read_env FAKRO_VENV_DIR)}"
APP_DIR="${APP_DIR:-/opt/fakro-bridge}"
VENV_DIR="${VENV_DIR:-/opt/tuya-env}"

if [[ -z "$DEPLOY_HOST" ]]; then
    echo "ERROR: FAKRO_DEPLOY_HOST is not set (set it in .env or the environment)." >&2
    exit 1
fi

RUN_DISCOVERY=false
if [[ "${1:-}" == "--discovery" ]]; then
    RUN_DISCOVERY=true
fi

echo "==> Repo:      $REPO_DIR"
echo "==> Target:    ${DEPLOY_HOST}:${APP_DIR}"
echo "==> Venv:      $VENV_DIR"

# 0. Make sure we have a local .env with secrets
if [[ ! -f "$REPO_DIR/.env" ]]; then
    echo "ERROR: no .env file in the repo directory." >&2
    echo "       Copy .env.example to .env and fill in the values." >&2
    exit 1
fi

# 1. Send the code (excluding .git, cache, logs and .env — .env goes separately in step 2)
#    We use tar over SSH instead of rsync, because the minimal LXC container has no rsync.
echo "==> [1/5] Syncing code (tar over SSH)..."
ssh "$DEPLOY_HOST" "mkdir -p ${APP_DIR}"
tar -cz \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.log' \
    --exclude '*.log.*' \
    --exclude '.env' \
    --exclude '.DS_Store' \
    -C "$REPO_DIR" . \
    | ssh "$DEPLOY_HOST" "tar -xz -C ${APP_DIR}"

# 2. Upload secrets (.env) with safe permissions
echo "==> [2/5] Uploading .env..."
scp -q "$REPO_DIR/.env" "${DEPLOY_HOST}:${APP_DIR}/.env"
ssh "$DEPLOY_HOST" "chmod 600 ${APP_DIR}/.env"

# 3. Ensure venv and dependencies
echo "==> [3/5] Python environment and dependencies..."
ssh "$DEPLOY_HOST" "bash -s" <<EOF
set -e
if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "    creating venv at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"
EOF

# 4. Install/refresh the systemd units
echo "==> [4/5] Installing systemd units..."
ssh "$DEPLOY_HOST" "bash -s" <<EOF
set -e
mkdir -p ${APP_DIR}/logs
cp ${APP_DIR}/deploy/systemd/fakro-bridge.service      /etc/systemd/system/
cp ${APP_DIR}/deploy/systemd/fakro-healthcheck.service /etc/systemd/system/
cp ${APP_DIR}/deploy/systemd/fakro-healthcheck.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now fakro-bridge.service
systemctl enable --now fakro-healthcheck.timer
systemctl restart fakro-bridge.service
EOF

# 5. (optional) publish MQTT Discovery
if [[ "$RUN_DISCOVERY" == true ]]; then
    echo "==> [5/5] Publishing MQTT Discovery..."
    ssh "$DEPLOY_HOST" "cd ${APP_DIR} && ${VENV_DIR}/bin/python discovery/ha_discovery.py"
else
    echo "==> [5/5] Skipping MQTT Discovery (run with --discovery to publish)."
fi

echo
echo "==> Done. Service status:"
ssh "$DEPLOY_HOST" "systemctl --no-pager --lines=0 status fakro-bridge.service" || true
echo
echo "Live logs:  ssh ${DEPLOY_HOST} 'tail -f ${APP_DIR}/logs/fakro_bridge.log'"

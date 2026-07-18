#!/usr/bin/env bash
#
# Deploy mostu Fakro-Tuya z Maca do kontenera LXC na Proxmoxie.
#
# Co robi:
#   1. Wysyła kod (tar po SSH) do katalogu aplikacji na kontenerze.
#   2. Wgrywa lokalny plik .env (sekrety) — osobno, bez trzymania go w repo.
#   3. Zapewnia środowisko Python (venv) i instaluje zależności.
#   4. Instaluje/aktualizuje jednostki systemd i restartuje usługę.
#
# Konfiguracja pochodzi z pliku .env (klucze FAKRO_DEPLOY_*), a można ją nadpisać
# zmiennymi środowiskowymi o tych samych nazwach:
#   FAKRO_DEPLOY_HOST   host SSH kontenera              (np. root@192.168.x.x)
#   FAKRO_DEPLOY_DIR    katalog aplikacji na kontenerze (/opt/fakro-bridge)
#   FAKRO_VENV_DIR      katalog wirtualnego środowiska  (/opt/tuya-env)
#
# Użycie:
#   ./deploy/deploy.sh              # deploy + restart usługi
#   ./deploy/deploy.sh --discovery  # dodatkowo publikuje MQTT Discovery do HA

set -euo pipefail

# Katalog główny repo (o poziom wyżej niż ten skrypt)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# Odczyt pojedynczego klucza z .env BEZ sourcowania pliku.
# (nie używamy `. .env`, bo wartości takie jak LOCAL_KEY zawierają znaki
#  specjalne — backtick itp. — które wywracają parser basha)
read_env() {
    [ -f "$REPO_DIR/.env" ] || return 0
    grep -E "^$1=" "$REPO_DIR/.env" | tail -n1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'
}

# Priorytet: zmienna środowiskowa > wartość z .env > wartość domyślna
DEPLOY_HOST="${FAKRO_DEPLOY_HOST:-$(read_env FAKRO_DEPLOY_HOST)}"
APP_DIR="${FAKRO_DEPLOY_DIR:-$(read_env FAKRO_DEPLOY_DIR)}"
VENV_DIR="${FAKRO_VENV_DIR:-$(read_env FAKRO_VENV_DIR)}"
APP_DIR="${APP_DIR:-/opt/fakro-bridge}"
VENV_DIR="${VENV_DIR:-/opt/tuya-env}"

if [[ -z "$DEPLOY_HOST" ]]; then
    echo "BŁĄD: brak FAKRO_DEPLOY_HOST (ustaw w .env lub w środowisku)." >&2
    exit 1
fi

RUN_DISCOVERY=false
if [[ "${1:-}" == "--discovery" ]]; then
    RUN_DISCOVERY=true
fi

echo "==> Repo:      $REPO_DIR"
echo "==> Cel:       ${DEPLOY_HOST}:${APP_DIR}"
echo "==> Venv:      $VENV_DIR"

# 0. Sprawdź, czy mamy lokalny .env z sekretami
if [[ ! -f "$REPO_DIR/.env" ]]; then
    echo "BŁĄD: brak pliku .env w katalogu repo." >&2
    echo "       Skopiuj .env.example do .env i uzupełnij wartości." >&2
    exit 1
fi

# 1. Wyślij kod (bez .git, cache, logów i .env — .env leci osobno w kroku 2)
#    Używamy tar po SSH zamiast rsync, bo minimalny kontener LXC nie ma rsync.
echo "==> [1/5] Synchronizacja kodu (tar po SSH)..."
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

# 2. Wgraj sekrety (.env) z bezpiecznymi uprawnieniami
echo "==> [2/5] Wgrywanie .env..."
scp -q "$REPO_DIR/.env" "${DEPLOY_HOST}:${APP_DIR}/.env"
ssh "$DEPLOY_HOST" "chmod 600 ${APP_DIR}/.env"

# 3. Zapewnij venv i zależności
echo "==> [3/5] Środowisko Python i zależności..."
ssh "$DEPLOY_HOST" "bash -s" <<EOF
set -e
if [ ! -x "${VENV_DIR}/bin/python" ]; then
    echo "    tworzę venv w ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"
EOF

# 4. Zainstaluj/odśwież jednostki systemd
echo "==> [4/5] Instalacja jednostek systemd..."
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

# 5. (opcjonalnie) opublikuj MQTT Discovery
if [[ "$RUN_DISCOVERY" == true ]]; then
    echo "==> [5/5] Publikacja MQTT Discovery..."
    ssh "$DEPLOY_HOST" "cd ${APP_DIR} && ${VENV_DIR}/bin/python discovery/ha_discovery.py"
else
    echo "==> [5/5] Pomijam MQTT Discovery (uruchom z --discovery, aby opublikować)."
fi

echo
echo "==> Gotowe. Status usługi:"
ssh "$DEPLOY_HOST" "systemctl --no-pager --lines=0 status fakro-bridge.service" || true
echo
echo "Podgląd logów na żywo:  ssh ${DEPLOY_HOST} 'journalctl -u fakro-bridge -f'"

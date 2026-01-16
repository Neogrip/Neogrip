#!/usr/bin/env bash
set -euo pipefail

APP_NAME="neogrip"
APP_USER="eegsvc"
APP_GROUP="eegsvc"

INSTALL_DIR="/opt/${APP_NAME}"
CONFIG_DIR="/etc/${APP_NAME}"
SECRETS_FILE="${CONFIG_DIR}/secrets.env"

SERVICE_NAME="${APP_NAME}.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_URL="${REPO_URL:-}"
REPO_REF="${REPO_REF:-main}"

ENTRYPOINT="${ENTRYPOINT:-main.py}"

# Optionnel: exécuter l’installateur Blinka officiel
INSTALL_BLINKA="${INSTALL_BLINKA:-0}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Erreur: Ce script doit être exécuté en root (ex: sudo ./install.sh)"
  exit 1
fi

echo "[1/10] Dépendances système…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  git \
  rsync \
  python3 \
  python3-venv \
  python3-pip \
  i2c-tools

echo "[2/10] Création de l'utilisateur système ${APP_USER}…"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

if ! getent group "${APP_GROUP}" >/dev/null 2>&1; then
  groupadd --system "${APP_GROUP}"
fi
usermod -g "${APP_GROUP}" "${APP_USER}" >/dev/null 2>&1 || true

# Accès I2C (important pour Adafruit ServoKit / PCA9685)
if getent group i2c >/dev/null 2>&1; then
  usermod -aG i2c "${APP_USER}" || true
fi

echo "[3/10] Installation / mise à jour dans ${INSTALL_DIR}…"
mkdir -p "${INSTALL_DIR}"

if [[ -n "${REPO_URL}" ]]; then
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    echo " - Repo déjà présent, pull en cours…"
    git -C "${INSTALL_DIR}" fetch --all --prune
    git -C "${INSTALL_DIR}" checkout "${REPO_REF}"
    git -C "${INSTALL_DIR}" pull --ff-only
  else
    echo " - Clone du repo…"
    rm -rf "${INSTALL_DIR:?}"/*
    git clone --branch "${REPO_REF}" --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
  fi
else
  echo " - Copie depuis le répertoire courant (${SCRIPT_DIR})…"
  rsync -a --delete \
    --exclude ".git" \
    --exclude "__pycache__" \
    --exclude ".venv" \
    --exclude "venv" \
    "${SCRIPT_DIR}/" "${INSTALL_DIR}/"
fi


# Setup des permissions
echo "[4/10] Permissions applicatives"
chown -R "${APP_USER}:${APP_GROUP}" "${INSTALL_DIR}"
chmod 755 "${INSTALL_DIR}"

if [[ ! -f "${INSTALL_DIR}/${ENTRYPOINT}" ]]; then
  echo "Erreur: entrypoint introuvable: ${INSTALL_DIR}/${ENTRYPOINT}"
  exit 1
fi

# Installation du fichier de secrets (config)
echo "[5/10] Déploiement de la configuration"
install -d -m 750 -o root -g "${APP_GROUP}" "${CONFIG_DIR}"

if [[ ! -f "${SECRETS_FILE}" ]]; then
  if [[ -f "${INSTALL_DIR}/deploy/secrets.env" ]]; then
    install -m 640 -o root -g "${APP_GROUP}" \
      "${INSTALL_DIR}/deploy/secrets.env" "${SECRETS_FILE}"
    echo " - Créé ${SECRETS_FILE} depuis deploy/secrets.env"
  else
    echo "Erreur: ${INSTALL_DIR}/deploy/secrets.env introuvable."
    exit 1
  fi
else
  echo " - ${SECRETS_FILE} déjà présent (conservé tel quel)"
fi

echo "[6/10] Installation Blinka Adafruit…"
if [[ "${INSTALL_BLINKA}" == "1" ]]; then
  # Installeur officiel recommandé par Adafruit
  # Il peut demander un reboot. :contentReference[oaicite:3]{index=3}
  apt-get install -y --no-install-recommends wget
  pip3 install --upgrade adafruit-python-shell
  wget -q -O /tmp/raspi-blinka.py \
    https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py
  sudo -E env PATH=$PATH python3 /tmp/raspi-blinka.py || true

  echo
  echo "Note: l’installateur Blinka peut nécessiter un redémarrage pour finaliser la config I2C/SPI."
  echo "Après reboot, relance: sudo ./install.sh"
  echo
fi

echo "[7/10] Création d'un environnement virtuel et installation des dépendances Python…"
PYTHON_SYS="/usr/bin/python3"
VENV_DIR="${INSTALL_DIR}/venv"
EXEC_PY="${PYTHON_SYS}"

if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    sudo -u "${APP_USER}" "${PYTHON_SYS}" -m venv "${VENV_DIR}"
  fi
  sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel
  sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"
  EXEC_PY="${VENV_DIR}/bin/python"
fi

echo "[8/10] Création du service NEOGRIP dans systemd"
if [[ ! -f "${INSTALL_DIR}/deploy/${SERVICE_NAME}" ]]; then
  echo "Erreur: ${INSTALL_DIR}/deploy/${SERVICE_NAME} introuvable."
  exit 1
fi

install -m 644 "${INSTALL_DIR}/deploy/${SERVICE_NAME}" "${SERVICE_DST}"
sed -i "s|^ExecStart=.*$|ExecStart=${EXEC_PY} ${INSTALL_DIR}/${ENTRYPOINT}|g" "${SERVICE_DST}"

echo "[9/10] Lancement et activation"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" >/dev/null

echo "[10/10] Démarrage de l'application"
if grep -qE '^EMOTIV_CLIENT_ID=\s*$' "${SECRETS_FILE}" || grep -qE '^EMOTIV_CLIENT_SECRET=\s*$' "${SECRETS_FILE}"; then
  echo
  echo "Installation terminée."
  echo "Action requise: édite ${SECRETS_FILE} et renseigne EMOTIV_CLIENT_ID / EMOTIV_CLIENT_SECRET, puis:"
  echo "  sudo systemctl start ${SERVICE_NAME}"
else
  systemctl restart "${SERVICE_NAME}"
  echo
  echo "Service démarré. Statut:"
  systemctl --no-pager --full status "${SERVICE_NAME}" || true
fi

echo
echo "Logs:"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
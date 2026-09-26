#!/usr/bin/env bash
# Préparation d'un poste Linux (ou d'Ubuntu sous WSL2) pour la formation PHAROS.
set -euo pipefail
DEPOT=${DEPOT:-git@github.com:akoudri/pharos-labs.git}
CIBLE=${CIBLE:-$HOME/pharos-labs}

echo "==> Paquets de base"
sudo apt-get update
sudo apt-get install -y ca-certificates curl git make

echo "==> Docker Engine et plugin Compose"
if ! command -v docker >/dev/null; then
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
sudo usermod -aG docker "$USER"
if grep -qi microsoft /proc/version; then
  # WSL : démarrage de Docker à l'ouverture d'Ubuntu (systemd activé par défaut sur Ubuntu 24.04 WSL)
  sudo systemctl enable --now docker || sudo service docker start
  # wslu fournit wslview : « make inspector » ouvre ainsi le navigateur Windows
  sudo apt-get install -y wslu
fi

echo "==> uv"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

echo "==> VS Code"
if grep -qi microsoft /proc/version; then
  echo "WSL détecté : VS Code s'installe côté Windows (outils/preparer-pc.ps1), pas ici."
elif command -v code >/dev/null; then
  echo "VS Code déjà installé."
elif command -v snap >/dev/null; then
  sudo snap install code --classic
else
  echo "snap introuvable : installer VS Code manuellement depuis https://code.visualstudio.com"
fi

echo "==> Dépôt pharos-labs"
[ -d "$CIBLE/.git" ] || git clone "$DEPOT" "$CIBLE"
cd "$CIBLE"
[ -f .env ] || cp .env.example .env

echo "==> Construction de l'image Python (peut prendre plusieurs minutes)"
if ! sudo -u "$USER" sg docker -c "make construire"; then
  echo "Construction de l'image échouée : relancer « make construire » dans $CIBLE et lire l'erreur." >&2
  exit 1
fi

echo "==> Préchargement de l'image de l'observateur"
FICHIERS_COMPOSE=$(for f in compose/*.yaml; do printf -- '-f %s ' "$f"; done)
if ! sudo -u "$USER" sg docker -c "docker compose -f compose.yaml $FICHIERS_COMPOSE pull observateur"; then
  echo "Préchargement de l'observateur impossible (réseau ?) : il sera téléchargé au premier « make up »."
fi

echo ""
echo "Terminé. Copier le .env du binôme dans $CIBLE/.env, puis : cd $CIBLE && make up && make lab0-up && make doctor"

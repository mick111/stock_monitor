#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_UNIT="stock-monitor.service"
TIMER_UNIT="stock-monitor.timer"

if [ "$(id -u)" -ne 0 ] && ! command -v sudo >/dev/null 2>&1; then
  echo "Erreur: sudo est requis pour installer les unites systemd." >&2
  exit 1
fi

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

link_unit() {
  local unit_file="$1"
  local source_path="$SCRIPT_DIR/$unit_file"
  local target_path="$SYSTEMD_DIR/$unit_file"

  if [ ! -f "$source_path" ]; then
    echo "Erreur: fichier introuvable: $source_path" >&2
    exit 1
  fi

  run_root ln -sfn "$source_path" "$target_path"
  echo "Lien cree: $target_path -> $source_path"
}

link_unit "$SERVICE_UNIT"
link_unit "$TIMER_UNIT"

run_root systemctl daemon-reload
run_root systemctl enable --now "$TIMER_UNIT"

echo "Installation terminee."
echo "Verification conseillee:"
echo "  systemctl status $TIMER_UNIT"
echo "  systemctl status $SERVICE_UNIT"

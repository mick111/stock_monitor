#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

ENV_FILES=(
  "$SCRIPT_DIR/monitor.env"
  "$SCRIPT_DIR/smtp.env"
)

for ENV_FILE in "${ENV_FILES[@]}"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
  fi
done

exec /usr/bin/python3 "$SCRIPT_DIR/monitor_stock.py" "$@"

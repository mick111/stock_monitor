#!/bin/bash
set -euo pipefail

ENV_FILES=(
  "/home/pi/Projects/hotas_stocks/monitor.env"
  "/home/pi/Projects/hotas_stocks/smtp.env"
)

for ENV_FILE in "${ENV_FILES[@]}"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$ENV_FILE"
    set +a
  fi
done

/usr/bin/python3 /home/pi/Projects/hotas_stocks/monitor_stock.py "$@"

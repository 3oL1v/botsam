#!/bin/bash
set -euo pipefail

PORT="${PORT:-8092}"
PY="${PY:-python3}"

mkdir -p logs dashboard/data user_data/logs

start_bot_loop() {
  local name="$1"
  local config="$2"
  local logfile="$3"

  (
    set +e
    while true; do
      echo "[${name}] starting Freqtrade dry-run bot with ${config}"
      freqtrade trade \
        --config "${config}" \
        --userdir user_data \
        --logfile "${logfile}"
      code="$?"
      echo "[${name}] exited with code ${code}; restarting in 30 seconds"
      sleep 30
    done
  ) &
}

start_bot_loop "volatility" "user_data/config_volatility_dry.json" "logs/volatility.log"
start_bot_loop "donchian" "user_data/config_donchian_dry.json" "logs/donchian.log"
start_bot_loop "vwap" "user_data/config_vwap_dry.json" "logs/vwap.log"

echo "[dashboard] starting Mini App dashboard on 0.0.0.0:${PORT}"
exec "${PY}" -m uvicorn dashboard.server:app --host 0.0.0.0 --port "${PORT}" --log-level info

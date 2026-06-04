#!/bin/bash
set -euo pipefail

PORT="${PORT:-8092}"
PY="${PY:-python3}"
SERVICE_ROLE="${SERVICE_ROLE:-all}"

mkdir -p logs dashboard/data user_data/logs

run_single_bot() {
  local name="$1"
  local config="$2"
  local logfile="$3"

  export FREQTRADE__API_SERVER__ENABLED=true
  export FREQTRADE__API_SERVER__LISTEN_IP_ADDRESS="${FREQTRADE_API_BIND:-::}"
  export FREQTRADE__API_SERVER__LISTEN_PORT="${PORT}"

  echo "[${name}] starting single Freqtrade dry-run service on [${FREQTRADE__API_SERVER__LISTEN_IP_ADDRESS}]:${PORT}"
  exec freqtrade trade \
    --config "${config}" \
    --userdir user_data \
    --logfile "${logfile}"
}

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

case "${SERVICE_ROLE}" in
  volatility)
    run_single_bot "volatility" "user_data/config_volatility_dry.json" "logs/volatility.log"
    ;;
  donchian)
    run_single_bot "donchian" "user_data/config_donchian_dry.json" "logs/donchian.log"
    ;;
  vwap)
    run_single_bot "vwap" "user_data/config_vwap_dry.json" "logs/vwap.log"
    ;;
  dashboard)
    echo "[dashboard] starting Mini App dashboard on 0.0.0.0:${PORT}"
    exec "${PY}" -m uvicorn dashboard.server:app --host 0.0.0.0 --port "${PORT}" --log-level info
    ;;
  all)
    start_bot_loop "volatility" "user_data/config_volatility_dry.json" "logs/volatility.log"
    start_bot_loop "donchian" "user_data/config_donchian_dry.json" "logs/donchian.log"
    start_bot_loop "vwap" "user_data/config_vwap_dry.json" "logs/vwap.log"

    echo "[dashboard] starting Mini App dashboard on 0.0.0.0:${PORT}"
    exec "${PY}" -m uvicorn dashboard.server:app --host 0.0.0.0 --port "${PORT}" --log-level info
    ;;
  *)
    echo "Unknown SERVICE_ROLE='${SERVICE_ROLE}'. Use all, dashboard, volatility, donchian or vwap." >&2
    exit 2
    ;;
esac

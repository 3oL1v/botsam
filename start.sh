#!/bin/bash
# =============================================================================
#  Стартовый скрипт контейнера (Railway).
#  1) Поднимает Freqtrade dry-run бота на 127.0.0.1:8081 (внутренний).
#  2) Поднимает dashboard/miniapp на 0.0.0.0:$PORT (публичный, отдаёт Railway).
#
#  ВАЖНО (безопасность): запускается ТОЛЬКО dry-run. Реальные деньги не нужны.
#  API-ключи биржи НЕ требуются для публичных цен.
# =============================================================================
set -e

CONFIG="user_data/config_binance_futures_dry.json"
STRATEGY="BinanceFuturesAtrStrategy"
PORT="${PORT:-8091}"

echo "[start] Запускаю Freqtrade dry-run бота (внутренний порт 8081)..."
freqtrade trade \
  --config "$CONFIG" \
  --userdir user_data \
  --strategy "$STRATEGY" \
  --logfile user_data/logs/binance_futures_dryrun.log &
BOT_PID=$!

# Ждём, пока бот поднимет свой REST API на 8081 (до ~60 сек)
echo "[start] Жду готовности API бота..."
for i in $(seq 1 60); do
  if curl -s -o /dev/null "http://127.0.0.1:8081/api/v1/ping"; then
    echo "[start] Бот готов."
    break
  fi
  sleep 1
done

echo "[start] Запускаю dashboard/miniapp на публичном порту $PORT..."
export DASHBOARD_CONFIG="$CONFIG"
# MINIAPP_ACCESS_TOKEN берётся из переменных окружения Railway.
exec python -m uvicorn dashboard.server:app --host 0.0.0.0 --port "$PORT" --log-level warning

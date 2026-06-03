#!/bin/bash
# =============================================================================
#  Стартовый скрипт контейнера (Railway).
#  ВАЖНО: dashboard поднимается СРАЗУ и слушает $PORT, чтобы Railway видел,
#  что приложение отвечает. Бот работает в фоне НЕЗАВИСИМО — если он упадёт
#  (например, Binance вернёт 451), dashboard всё равно останется доступен и
#  покажет статус "бот недоступен" вместо "Application failed to respond".
#
#  Безопасность: только dry-run. Реальные деньги/ключи не нужны.
# =============================================================================

CONFIG="user_data/config_binance_futures_dry.json"
STRATEGY="CrossSqueezeExpansion4HFilter15m"
PORT="${PORT:-8091}"

mkdir -p user_data/logs

# Работаем как ftuser: его python видит uvicorn/fastapi из ~/.local.
PY="python3"

# 1) Бот — в фоне, с авто-перезапуском (на случай временного 451 у биржи).
#    НЕ блокирует старт dashboard.
(
  while true; do
    echo "[start] Запускаю Freqtrade dry-run бота..."
    freqtrade trade \
      --config "$CONFIG" \
      --userdir user_data \
      --strategy "$STRATEGY" \
      --logfile user_data/logs/binance_futures_dryrun.log
    echo "[start] Бот завершился (код $?). Перезапуск через 30 сек..."
    sleep 30
  done
) &

# 2) Dashboard/miniapp — СРАЗУ на публичном порту (foreground, держит контейнер).
#    MINIAPP_ACCESS_TOKEN берётся из переменных окружения Railway.
export DASHBOARD_CONFIG="$CONFIG"
echo "[start] Запускаю dashboard/miniapp на 0.0.0.0:$PORT ..."
exec "$PY" -m uvicorn dashboard.server:app --host 0.0.0.0 --port "$PORT" --log-level warning

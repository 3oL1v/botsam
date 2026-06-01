# =============================================================================
#  Dockerfile для Railway: Freqtrade (dry-run) + dashboard/miniapp в одном
#  контейнере. Бот слушает 127.0.0.1:8081 (внутри), dashboard публикуется
#  наружу на $PORT.
#
#  ВАЖНО: базовый образ ставит freqtrade и его зависимости (включая uvicorn,
#  fastapi, ccxt, requests) в ~/.local пользователя ftuser. Поэтому работаем
#  именно как ftuser (НЕ root) — иначе python не видит эти пакеты.
# =============================================================================
FROM freqtradeorg/freqtrade:stable

WORKDIR /freqtrade

# Копируем проект с владельцем ftuser, чтобы бот мог писать логи/БД.
# (.dockerignore исключает секреты и локальные данные.)
COPY --chown=ftuser:ftuser user_data/ /freqtrade/user_data/
COPY --chown=ftuser:ftuser dashboard/ /freqtrade/dashboard/
COPY --chown=ftuser:ftuser start.sh /freqtrade/start.sh

USER root
RUN chmod +x /freqtrade/start.sh
USER ftuser

# Railway передаёт публичный порт в $PORT (по умолчанию 8091 для локали).
ENV PORT=8091
EXPOSE 8091

ENTRYPOINT ["/freqtrade/start.sh"]

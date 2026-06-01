# =============================================================================
#  Dockerfile для Railway: Freqtrade (dry-run) + dashboard/miniapp в одном
#  контейнере. Бот слушает 127.0.0.1:8081 (внутри), dashboard публикуется
#  наружу на $PORT (Railway сам подставит порт).
# =============================================================================
FROM freqtradeorg/freqtrade:stable

# Запускаемся под root, чтобы свободно писать логи/БД в /freqtrade.
USER root

# Зависимости dashboard (fastapi, uvicorn, ccxt, requests) уже входят в образ
# freqtrade, поэтому отдельный pip install не нужен — это исключает риск
# установки в неверный Python-venv.

WORKDIR /freqtrade

# Копируем проект (см. .dockerignore — секреты и данные не попадают)
COPY user_data/ /freqtrade/user_data/
COPY dashboard/ /freqtrade/dashboard/
COPY start.sh /freqtrade/start.sh

RUN chmod +x /freqtrade/start.sh

# Railway передаёт публичный порт в $PORT. Dashboard слушает его.
ENV PORT=8091
EXPOSE 8091

ENTRYPOINT ["/freqtrade/start.sh"]

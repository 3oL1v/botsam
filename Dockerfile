# =============================================================================
#  Dockerfile для Railway: Freqtrade (dry-run) + dashboard/miniapp в одном
#  контейнере. Бот слушает 127.0.0.1:8081 (внутри), dashboard публикуется
#  наружу на $PORT (Railway сам подставит порт).
# =============================================================================
FROM freqtradeorg/freqtrade:stable

USER root

# Доп. зависимости для dashboard (fastapi/uvicorn уже есть во freqtrade-образе,
# ставим недостающие на всякий случай).
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.29" "ccxt>=4.5" "requests>=2.31"

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

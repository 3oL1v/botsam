# Деплой на Railway

Цель: один Railway service запускает 3 Freqtrade dry-run процесса и один Mini App dashboard. Наружу публикуется только dashboard. Freqtrade REST API слушает `127.0.0.1` внутри контейнера.

## Важно

- Реальная торговля не включается: во всех конфигах `dry_run: true`.
- Binance Futures может заблокировать Railway/cloud IP ошибкой `451 restricted location`. После деплоя нужно проверять deploy logs и `/api/health`.
- Railway Quick/Generated Domain даст постоянный HTTPS URL для Telegram Mini App. Cloudflare quick tunnel на Railway не нужен.

## Через Railway CLI

```powershell
npm install -g @railway/cli
railway login
railway link
railway variables set MINIAPP_ACCESS_TOKEN="длинный_секретный_токен"
railway up
```

После деплоя:

```powershell
railway logs
railway open
```

В Railway UI открой service -> Settings -> Networking -> Generate Domain.

Mini App URL:

```text
https://ТВОЙ-ДОМЕН.up.railway.app/miniapp?access=ТВОЙ_ТОКЕН
```

Health URL:

```text
https://ТВОЙ-ДОМЕН.up.railway.app/api/health?access=ТВОЙ_ТОКЕН
```

Log tail URL:

```text
https://ТВОЙ-ДОМЕН.up.railway.app/api/logs?name=donchian&lines=120&access=ТВОЙ_ТОКЕН
```

## Через GitHub

1. Закоммить и запушь изменения в `main`.
2. Railway -> New Project -> Deploy from GitHub repo -> выбери `botsam`.
3. Variables -> добавь `MINIAPP_ACCESS_TOKEN`.
4. Settings -> Networking -> Generate Domain.
5. Проверяй Deploy Logs.

## Что должно быть в логах

Ищи строки:

```text
[volatility] starting Freqtrade dry-run bot
[donchian] starting Freqtrade dry-run bot
[vwap] starting Freqtrade dry-run bot
[dashboard] starting Mini App dashboard
```

Если Binance заблокирует облачный IP, в логах Freqtrade будет ошибка про `451` или невозможность загрузить markets. Dashboard при этом может быть живым, но `/api/health` покажет, что боты недоступны.

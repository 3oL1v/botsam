# Деплой на Railway

Цель: Railway запускает 3 Freqtrade dry-run бота и один Mini App dashboard. Наружу публикуется только dashboard. Боты доступны dashboard через Railway private networking.

## Важно

- Реальная торговля не включается: во всех конфигах `dry_run: true`.
- Binance Futures может заблокировать Railway/cloud IP ошибкой `451 restricted location`. После деплоя нужно проверять deploy logs и `/api/health`.
- Railway Quick/Generated Domain даст постоянный HTTPS URL для Telegram Mini App. Cloudflare quick tunnel на Railway не нужен.
- Один Railway service с 3 Freqtrade процессами может флапать по памяти. Рекомендуемая схема: 4 services из одного repo.

## Рекомендуемая схема: 4 Railway services

Создай в одном Railway project четыре services из одного GitHub repo:

| Service name | Variables |
|---|---|
| `dashboard` | `SERVICE_ROLE=dashboard`, `MINIAPP_ACCESS_TOKEN=...`, `BOT_VOLATILITY_URL=http://volatility.railway.internal:8080/api/v1`, `BOT_DONCHIAN_URL=http://donchian.railway.internal:8080/api/v1`, `BOT_VWAP_URL=http://vwap.railway.internal:8080/api/v1` |
| `volatility` | `SERVICE_ROLE=volatility`, `PORT=8080` |
| `donchian` | `SERVICE_ROLE=donchian`, `PORT=8080` |
| `vwap` | `SERVICE_ROLE=vwap`, `PORT=8080` |

Public domain генерируй только для `dashboard`. Для трёх bot services публичный домен не нужен.

Railway private networking использует внутренние имена вида `service-name.railway.internal`; HTTP внутри private network должен быть обычный `http`, не `https`.

## Через Railway CLI

```powershell
npm install -g @railway/cli
railway login
railway link
railway variables set MINIAPP_ACCESS_TOKEN="длинный_секретный_токен"
railway up
```

CLI вариант выше подходит для одного service. Для рекомендуемой 4-service схемы проще создать/продублировать services в Railway UI и задать `SERVICE_ROLE`.

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

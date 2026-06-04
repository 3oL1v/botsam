# Freqtrade Dry-Run: 3 стратегии + Telegram Mini App

Текущая система работает локально и только в бумажном режиме. Реальные деньги не используются: во всех рабочих конфигах `dry_run: true`.

## Что запущено

- Биржа: Binance USD-M Futures.
- Режим: futures, isolated margin, dry-run.
- Виртуальный баланс: 100 USDT на каждого бота.
- Пары: `BTC/USDT:USDT`, `ETH/USDT:USDT`, `SOL/USDT:USDT`, `BNB/USDT:USDT`.
- Стратегии:
  - `VolatilitySqueezeBreakoutAggressive` на порту `8081`.
  - `DonchianVolumeBurst5m` на порту `8082`.
  - `VWAPPullbackMomentumScalp` на порту `8083`.
- Mini App dashboard: `127.0.0.1:8092`.
- HTTPS для Telegram Mini App: Cloudflare Quick Tunnel.

## Основные файлы

- Стратегии: `user_data/strategies/`.
- Конфиги ботов:
  - `user_data/config_volatility_dry.json`
  - `user_data/config_donchian_dry.json`
  - `user_data/config_vwap_dry.json`
- Mini App: `dashboard/server.py`, `dashboard/static/`.
- Память сделок: `dashboard/data/trade_journal.sqlite`.
- Логи: `logs/`.

## Как запустить

```powershell
.\run_dryrun.ps1
.\run_https_tunnel.ps1
```

Локальная ссылка:

```text
http://127.0.0.1:8092/miniapp?access=TOKEN_ИЗ_ENV
```

Временная HTTPS-ссылка Cloudflare появится в выводе `run_https_tunnel.ps1`.

## Как остановить

```powershell
.\stop_dryrun_stack.ps1
```

Скрипт остановит локальные порты `8081`, `8082`, `8083`, `8092` и процесс `cloudflared`.

## Как проверить

```powershell
Invoke-WebRequest http://127.0.0.1:8081/api/v1/ping
Invoke-WebRequest http://127.0.0.1:8082/api/v1/ping
Invoke-WebRequest http://127.0.0.1:8083/api/v1/ping
```

Dashboard API:

```powershell
Invoke-WebRequest "http://127.0.0.1:8092/api/health?access=TOKEN_ИЗ_ENV"
Invoke-WebRequest "http://127.0.0.1:8092/api/miniapp?access=TOKEN_ИЗ_ENV"
Invoke-WebRequest "http://127.0.0.1:8092/api/journal?access=TOKEN_ИЗ_ENV"
Invoke-WebRequest "http://127.0.0.1:8092/api/logs?name=donchian&access=TOKEN_ИЗ_ENV"
```

## Память сделок

Dashboard сохраняет каждую увиденную сделку в SQLite:

- стратегия;
- бот;
- пара;
- long/short;
- entry tag;
- цена входа и выхода;
- PnL;
- причина выхода;
- snapshot параметров стратегии на момент сделки.

Это нужно, чтобы позже менять параметры стратегии и не терять понимание, по каким настройкам была открыта старая сделка.

## Важные ограничения

- Не ставить `dry_run` в `false`.
- Не публиковать Freqtrade REST API наружу. Наружу идёт только Mini App dashboard.
- Cloudflare Quick Tunnel временный: ссылка меняется после перезапуска.
- Для постоянного Telegram Mini App нужен постоянный домен или named Cloudflare Tunnel.
- Три dry-run бота могут одновременно открыть виртуальные сделки по одной паре. Для live-режима такая архитектура без общего риск-контроля не подходит.
- На Railway предпочтительно запускать 4 services: `dashboard`, `volatility`, `donchian`, `vwap`. Один контейнер с тремя Freqtrade процессами может флапать по памяти.

# Freqtrade Dry-Run: 3 стратегии + Telegram Mini App

Бумажный режим (paper trading). Реальные деньги **не используются** — во всех
рабочих конфигах `dry_run: true`. Это стенд для обкатки инфраструктуры и
наблюдения за стратегиями, не торговый продукт.

> **Честный статус по стратегиям.** Все три активные стратегии прогнаны строгим
> бэктестом на реальных данных Binance 2024–2026 (комиссии 0.05%/сторону +
> проскальзывание 0.02% + funding, без look-ahead и подгонки) — см.
> `research/aggressive_futures_lab/`. На holdout 2026 **все убыточны**
> (Volatility −27%, Donchian −94%, VWAP −90%): высокочастотный скальпинг
> съедается издержками. Поэтому это dry-run-исследование, а не заработок.

## Что запущено

- Биржа: Binance USD-M Futures.
- Режим: futures, isolated margin, dry-run.
- Виртуальный баланс: 100 USDT на каждого бота.
- Пары: `BTC/USDT:USDT`, `ETH/USDT:USDT`, `SOL/USDT:USDT`, `BNB/USDT:USDT`.
- Боты (каждый — отдельный Freqtrade-процесс со своим REST API):
  - `VolatilitySqueezeBreakoutAggressive` — порт `8081`.
  - `DonchianVolumeBurst5m` — порт `8082`.
  - `VWAPPullbackMomentumScalp` — порт `8083`.
- Mini App dashboard: `127.0.0.1:8092` (агрегирует 3 бота, наружу публикуется только он).

## Основные файлы

- Стратегии: `user_data/strategies/` (+ общий `lab_base.py`).
- Конфиги ботов: `user_data/config_volatility_dry.json`, `config_donchian_dry.json`, `config_vwap_dry.json`.
- Mini App: `dashboard/server.py`, `dashboard/static/`.
- Память сделок: `dashboard/data/trade_journal.sqlite`.
- Логи: `logs/`.
- Запуск контейнера/Railway: `start.sh` (роли `SERVICE_ROLE=all|dashboard|volatility|donchian|vwap`), `Dockerfile`.
- Деплой 24/7: `docker-compose.yml`, `Caddyfile`, `DEPLOY_ORACLE_RU.md`.
- Исследование стратегий: `research/aggressive_futures_lab/`.

## Запуск локально (бесплатно, пока ПК включён)

```powershell
.\run_dryrun.ps1        # 3 бота + dashboard
.\run_https_tunnel.ps1  # временный HTTPS через Cloudflare Quick Tunnel
.\stop_dryrun_stack.ps1 # остановить всё (порты 8081-8083, 8092 + cloudflared)
```

Локальная ссылка: `http://127.0.0.1:8092/miniapp?access=ТОКЕН_ИЗ_ENV`.
HTTPS-ссылка `…trycloudflare.com` появится в выводе `run_https_tunnel.ps1`
(она **временная** — меняется при каждом перезапуске туннеля).

## Деплой 24/7 без включённого ПК

Рекомендуемый бесплатный путь — **Oracle Cloud Always Free** (ARM ВМ, до 24 ГБ
RAM, бесплатно навсегда; карта только для верификации, списаний нет). Полная
пошаговая инструкция: **`DEPLOY_ORACLE_RU.md`**. Кратко:

1. Аккаунт Oracle, регион **Singapore/Tokyo** (важно из-за геоблока Binance 451).
2. ARM ВМ (VM.Standard.A1.Flex, Ubuntu 22.04), открыть порты 80/443.
3. Постоянный домен — бесплатный поддомен **DuckDNS** на IP ВМ.
4. На ВМ: `git clone`, создать `.env` (токен + домен), `docker compose up -d --build`.
   `docker-compose.yml` поднимает весь стек (`SERVICE_ROLE=all`) + Caddy с
   авто-HTTPS (Let's Encrypt) на постоянном домене.

Постоянная ссылка получится вида `https://ваш-поддомен.duckdns.org/miniapp?access=ТОКЕН`.

> Railway раньше тоже использовался (`DEPLOY_RAILWAY_RU.md`, схема из 4 services),
> но его free-режим закрылся (требует оплату). Актуальный бесплатный 24/7 — Oracle.

## Исследование стратегий

`research/aggressive_futures_lab/` — изолированный модуль (не влияет на боевой
стек): 6 агрессивных long/short стратегий, реальные данные Binance, честный
backtest на штатном движке Freqtrade, рейтинг по validation/holdout. Итоговый
отчёт: `research/aggressive_futures_lab/reports/RANKING_REPORT.md`. Главный
вывод — ни одна стратегия не показала преимущества после издержек.

## Проверка

```powershell
Invoke-WebRequest "http://127.0.0.1:8092/api/health?access=ТОКЕН_ИЗ_ENV"
Invoke-WebRequest "http://127.0.0.1:8092/api/miniapp?access=ТОКЕН_ИЗ_ENV"
Invoke-WebRequest "http://127.0.0.1:8092/api/logs?name=donchian&access=ТОКЕН_ИЗ_ENV"
```
`/api/health` должен показать 3 бота со `state: running`, `dry_run: true`.

## Память сделок

Dashboard сохраняет каждую увиденную сделку в SQLite: стратегия, бот, пара,
long/short, entry tag, цены входа/выхода, PnL, причина выхода и snapshot
параметров стратегии на момент сделки — чтобы при смене параметров не терять
контекст старых сделок.

## Важные ограничения

- **Никогда** не ставить `dry_run` в `false` без отдельного решения. Реальная торговля не ведётся.
- Freqtrade REST API ботов наружу не публикуется — только Mini App dashboard (на Oracle публичны лишь 80/443 → Caddy → dashboard).
- Cloudflare Quick Tunnel временный; постоянный адрес — через DuckDNS + Caddy на сервере.
- Три dry-run бота могут одновременно открыть виртуальные сделки по одной паре. Для live такая схема без общего риск-контроля не годится.
- Секреты (токен Mini App, ключи) — только в `.env`/переменных окружения, не в коммитах.

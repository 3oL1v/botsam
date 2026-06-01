# Freqtrade Dry-Run: BingX Spot + Binance Futures

Локальный проект Freqtrade для бумажной торговли.
Реальная торговля здесь не включается: в конфигах стоит `"dry_run": true`.

---

## ⭐ КРАТКИЙ СТАРТ (читать первым)

**Что это:** бумажный (виртуальный) торговый бот на живых ценах. Реальные деньги НЕ используются.
**Главный рабочий контур:** Binance Futures (long/short, плечо) — порт **8081**.
Второй контур (BingX spot) — порт **8080**, оставлен для экспериментов.

### Проверить, что бот жив
```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/v1/ping   # ждём {"status":"pong"}
```

### Запустить Binance Futures dry-run (если не запущен)
```powershell
cd C:\trade2
$env:PYTHONUTF8 = "1"
.\.venv\Scripts\freqtrade.exe trade --config user_data\config_binance_futures_dry.json --userdir user_data --strategy BinanceFuturesAtrStrategy --logfile user_data\logs\binance_futures_dryrun.log
```
> ⚠️ Перед запуском убедись, что бот ещё НЕ работает (иначе будет конфликт порта и общей БД):
> ```powershell
> Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue
> ```
> Если порт занят — бот уже запущен, второй раз стартовать не нужно.

### Веб-интерфейс (freqUI)
- Binance Futures: <http://127.0.0.1:8081>
- BingX spot: <http://127.0.0.1:8080>
- Логин/пароль — в соответствующем конфиге, секция `api_server` (`username` / `password`).

### Остановить бота
```powershell
Get-NetTCPConnection -LocalPort 8081 -State Listen | Select-Object OwningProcess   # узнать PID
Stop-Process -Id <PID>                                                              # остановить
```

### ⚠️ Статус стратегии (важно!)
Обе стратегии в бэктесте **убыточны** (Profit factor ~0.8, итог в минус и на раннем, и на свежем периоде). Инфраструктура исправна, но **торгового преимущества у стратегий нет**. Dry-run запущен для проверки инфраструктуры, НЕ ради прибыли. Реальные деньги включать НЕЛЬЗЯ — см. чеклист в конце файла.

> Полная справка (дашборды, Telegram Mini App, загрузка данных, параметры) — ниже.

---

Сейчас есть два отдельных контура:

- BingX SPOT dry-run: FreqUI `http://127.0.0.1:8080`, dashboard `http://127.0.0.1:8090`.
- Binance Futures dry-run: FreqUI `http://127.0.0.1:8081`, dashboard `http://127.0.0.1:8091`.

## Что установлено

- Freqtrade: `2026.5`
- Способ запуска: локальный Python venv, потому что Docker в системе не найден.
- FreqUI: установлен, версия `3.0.0`.
- Биржа: `bingx`
- Режим: `spot`
- Пары: `BTC/USDT`, `ETH/USDT`, `TONCOIN/USDT`, `HYPE/USDT`, `XLM/USDT`, `XRP/USDT`
- Таймфрейм: `1h`
- Виртуальный депозит: `1000 USDT`
- Дополнительно настроен Binance Futures dry-run: `binance`, `futures`, `isolated`, пары `BTC/USDT:USDT`, `ETH/USDT:USDT`, `SOL/USDT:USDT`, `BNB/USDT:USDT`, `XRP/USDT:USDT`, `TON/USDT:USDT`, `DOGE/USDT:USDT`, `LINK/USDT:USDT`, `ADA/USDT:USDT`, `AVAX/USDT:USDT`.

## Важные файлы

- `user_data/config.json` - основной конфиг Freqtrade.
- `user_data/config_binance_futures_dry.json` - конфиг Binance Futures dry-run.
- `.env` - место для API ключей. Сейчас там плейсхолдеры.
- `user_data/strategies/atr_trend_strategy.py` - стратегия.
- `user_data/strategies/binance_futures_atr_strategy.py` - futures-стратегия long/short с плечом 1x.
- `user_data/logs/dryrun.log` - лог запущенного dry-run.
- `user_data/logs/binance_futures_dryrun.log` - лог Binance Futures dry-run.
- `tradesv3.binance_futures_dryrun.sqlite` - отдельная dry-run база Binance Futures.
- `user_data/data/bingx/` - скачанные свечи.
- `user_data/data/binance/futures/` - скачанные futures-свечи, mark и funding данные Binance.
- `user_data/backtest_results/` - результаты бэктестов.

## API ключи BingX

В dry-run ключи не обязательны: публичные цены доступны без них.

Если позже добавляешь ключи:

1. Открой BingX.
2. Перейди в `Account -> API Management`.
3. Создай API key.
4. Разреши только `Read` и `Spot Trading`.
5. Не включай `Withdraw`.
6. Впиши значения в `.env`:

```powershell
FREQTRADE__EXCHANGE__KEY=...
FREQTRADE__EXCHANGE__SECRET=...
```

## Запуск dry-run

```powershell
cd C:\trade2
.\.venv\Scripts\python.exe -m freqtrade trade --config user_data\config.json --userdir user_data --strategy AtrTrendStrategy --logfile user_data\logs\dryrun.log
```

Сейчас бот уже запущен в фоне. FreqUI доступен здесь:

```text
http://127.0.0.1:8080
```

Логин из `user_data/config.json`:

```text
username: freqtrader
password: change_this_local_password
```

## Упрощенный dashboard

Помимо стандартного FreqUI на `8080`, добавлен отдельный минималистичный интерфейс на `8090`:

```text
http://127.0.0.1:8090
```

Что показывает:

- выбранную пару из whitelist;
- текущую цену, bid/ask, spread и 24h volume;
- линейный график цены по 1h свечам;
- RSI(14) с уровнями 35 и 70;
- стакан BingX spot;
- Fear & Greed Index;
- funding rate как публичную справочную метрику perpetual-рынка;
- статус Freqtrade dry-run, открытые виртуальные сделки и profit.

Запуск:

```powershell
cd C:\trade2
.\.venv\Scripts\python.exe -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8090
```

Проверка:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/api/pairs
Invoke-RestMethod 'http://127.0.0.1:8090/api/market?pair=BTC%2FUSDT'
```

Остановка:

```powershell
Get-NetTCPConnection -LocalPort 8090 | Select-Object OwningProcess
Stop-Process -Id <PID>
```

Dashboard не отправляет ордера. Funding показывается только как информационный публичный показатель.

## Binance Futures dry-run

Это отдельный контур для проверки futures на виртуальных средствах. Он не заменяет BingX spot.

Главные файлы:

- `user_data/config_binance_futures_dry.json`
- `user_data/strategies/binance_futures_atr_strategy.py`
- `user_data/logs/binance_futures_dryrun.log`

Ключевые настройки:

```json
"dry_run": true,
"dry_run_wallet": 1000,
"db_url": "sqlite:///tradesv3.binance_futures_dryrun.sqlite",
"trading_mode": "futures",
"margin_mode": "isolated",
"liquidation_buffer": 0.05
```

Стратегия принудительно возвращает плечо `1.0`, то есть первый futures-контур работает без усиления риска.

Запуск Binance Futures dry-run:

```powershell
cd C:\trade2
.\.venv\Scripts\python.exe -m freqtrade trade --config user_data\config_binance_futures_dry.json --userdir user_data --strategy BinanceFuturesAtrStrategy --logfile user_data\logs\binance_futures_dryrun.log
```

FreqUI:

```text
http://127.0.0.1:8081
```

Упрощенный dashboard:

```powershell
cd C:\trade2
$env:DASHBOARD_CONFIG='user_data\config_binance_futures_dry.json'
.\.venv\Scripts\python.exe -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8091
```

Открыть:

```text
http://127.0.0.1:8091
```

Проверка:

```powershell
Invoke-RestMethod http://127.0.0.1:8081/api/v1/ping
Invoke-RestMethod http://127.0.0.1:8091/api/pairs
Invoke-RestMethod 'http://127.0.0.1:8091/api/market?pair=BTC%2FUSDT%3AUSDT'
Get-Content user_data\logs\binance_futures_dryrun.log -Tail 80
```

Если позже добавляешь Binance API ключи, права должны быть только `Read` и `Futures trading`. Вывод средств (`Withdraw`) не включать. Для Binance Futures Freqtrade ожидает настройки аккаунта `One-way Mode` и `Single-Asset Mode`; бот проверяет их при старте, но сам не меняет.

## Результат Binance Futures бэктеста

Период `2024-06-01..2026-06-01`, пары из Binance futures whitelist, таймфрейм `1h`:

- Сделок: `988`
- Win rate: `34.7%`
- Profit factor: `0.84`
- Итог: `-56.27%`
- Max drawdown: `58.57%`

Вывод: futures-инфраструктура работает, но текущая стратегия не годится для реальной торговли. Это технический каркас для dry-run, UI и дальнейших экспериментов, а не прибыльная торговая система.

Разделение на ранний и свежий период:

- `2024-06-17..2025-06-01`: `510` сделок, win rate `35.3%`, profit factor `0.84`, итог `-36.86%`, max drawdown `40.70%`.
- `2025-06-01..2026-05-31`: `480` сделок, win rate `33.3%`, profit factor `0.82`, итог `-36.46%`, max drawdown `39.75%`.

Out-of-sample не держится: свежий год почти такой же плохой, как ранний.

## Telegram Mini App monitor

Добавлена отдельная мобильная read-only страница для телефона:

```text
http://127.0.0.1:8092/miniapp?access=<MINIAPP_ACCESS_TOKEN>
```

Файлы:

- `dashboard/static/miniapp.html`
- `dashboard/static/miniapp.css`
- `dashboard/static/miniapp.js`
- endpoint данных: `/api/miniapp`

Страница показывает:

- статус Binance Futures dry-run;
- виртуальный P/L и баланс;
- число открытых сделок;
- открытые dry-run сделки;
- историю закрытых dry-run сделок;
- BTC futures цену, RSI, Fear & Greed и funding.

Страница не отправляет торговые команды. Это только мониторинг.

Токен доступа лежит в `.env`:

```powershell
MINIAPP_ACCESS_TOKEN=...
```

Без токена API возвращает `401`, поэтому публичный URL должен быть с `?access=...`.

Запуск локального miniapp-сервера:

```powershell
cd C:\trade2
$env:DASHBOARD_CONFIG='user_data\config_binance_futures_dry.json'
.\.venv\Scripts\python.exe -m uvicorn dashboard.server:app --host 127.0.0.1 --port 8092
```

Текущий HTTPS-туннель через Cloudflare Quick Tunnel:

```text
https://pop-participated-object-fri.trycloudflare.com/miniapp?access=<MINIAPP_ACCESS_TOKEN>
```

Важно: Quick Tunnel бесплатный и удобный для теста, но URL временный. После перезапуска `cloudflared` адрес может измениться. Для постоянного Telegram Mini App лучше потом сделать постоянный домен или named tunnel.

Запуск HTTPS-туннеля:

```powershell
cloudflared tunnel --url http://127.0.0.1:8092 --no-autoupdate
```

Остановка:

```powershell
Get-Process cloudflared
Stop-Process -Id <PID>
Get-NetTCPConnection -LocalPort 8092 | Select-Object OwningProcess
Stop-Process -Id <PID>
```

## Проверить, что бот жив

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/v1/ping
Get-Content user_data\logs\dryrun.log -Tail 80
```

Ожидаемый ping:

```json
{"status":"pong"}
```

В логе должны быть строки:

```text
Runmode set to dry_run.
Dry run is enabled
state='RUNNING'
```

## Остановить бота

Посмотреть процесс, который слушает нужный порт:

```powershell
Get-NetTCPConnection -LocalPort 8080 | Select-Object LocalAddress,LocalPort,State,OwningProcess
Get-NetTCPConnection -LocalPort 8081 | Select-Object LocalAddress,LocalPort,State,OwningProcess
Get-NetTCPConnection -LocalPort 8091 | Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Остановить по PID:

```powershell
Stop-Process -Id <PID>
```

PID меняется при каждом старте, поэтому перед остановкой всегда сначала смотри `OwningProcess`.

## Если FreqUI снова не установлен

Стандартная команда:

```powershell
.\.venv\Scripts\python.exe -m freqtrade install-ui
```

В этом окружении она может падать из-за нестабильного TLS-соединения к GitHub через VPN. В таком случае нужно повторить установку или использовать ручной fallback, который скачивает релиз FreqUI и распаковывает его в:

```text
.venv\Lib\site-packages\freqtrade\rpc\api_server\ui\installed
```

## Скачать данные

```powershell
.\.venv\Scripts\python.exe -m freqtrade download-data --config user_data\config.json --userdir user_data --exchange bingx --pairs BTC/USDT ETH/USDT --timeframes 1h --timerange 20230601-20260601 --trading-mode spot
```

Фактически BingX через текущий Freqtrade/CCXT отдал данные только с `2025-06-05 15:00 UTC` до `2026-05-31 22:00 UTC`.

## Бэктест

Общий прогон:

```powershell
.\.venv\Scripts\python.exe -m freqtrade backtesting --config user_data\config.json --userdir user_data --strategy AtrTrendStrategy --timerange 20250605-20260601 --timeframe 1h --enable-protections --export trades
```

Разделение периода:

```powershell
.\.venv\Scripts\python.exe -m freqtrade backtesting --config user_data\config.json --userdir user_data --strategy AtrTrendStrategy --timerange 20250605-20251201 --timeframe 1h --enable-protections
.\.venv\Scripts\python.exe -m freqtrade backtesting --config user_data\config.json --userdir user_data --strategy AtrTrendStrategy --timerange 20251201-20260601 --timeframe 1h --enable-protections
```

## Результаты текущей стратегии

Общий период `2025-06-22..2026-05-31`:

- Сделок: `89`
- Win rate: `28.1%`
- Profit factor: `0.54`
- Итог: `-24.57%`
- Max drawdown: `28.50%`

Ранний период:

- Сделок: `40`
- Итог: `-10.21%`
- Profit factor: `0.60`
- Max drawdown: `13.37%`

Последний доступный период:

- Сделок: `49`
- Итог: `-15.99%`
- Profit factor: `0.48`
- Max drawdown: `17.47%`

Вывод: стратегия не проходит проверку. Сделок меньше 100 на общем периоде, статистика слабая, а доходность отрицательная и на раннем, и на последнем периоде.

## Как менять параметры

Пары меняются в `user_data/config.json`:

```json
"pair_whitelist": ["BTC/USDT", "ETH/USDT", "TONCOIN/USDT", "HYPE/USDT", "XLM/USDT", "XRP/USDT"]
```

Важно: TON на BingX spot в Freqtrade называется `TONCOIN/USDT`, а не `TON/USDT`.

Таймфрейм меняется в `user_data/config.json` и в стратегии:

```json
"timeframe": "1h"
```

```python
timeframe = "1h"
```

Параметры стратегии меняются в `user_data/strategies/atr_trend_strategy.py`:

```python
ema_fast = 50
ema_slow = 200
rsi_period = 14
rsi_entry = 35
rsi_exit = 70
atr_period = 14
atr_multiplier = 2.0
risk_reward = 1.5
risk_per_trade = 0.01
```

## Почему stake_amount unlimited

В конфиге стоит:

```json
"stake_amount": "unlimited"
```

Но стратегия сама считает размер позиции через `custom_stake_amount`.
Расчет: если депозит 1000 USDT, риск 1% = 10 USDT. Если стоп на расстоянии 5%, позиция будет `10 / 0.05 = 200 USDT`.

## Stoploss on exchange

В конфиге включено:

```json
"stoploss": "market",
"stoploss_on_exchange": true
```

По актуальной документации Freqtrade BingX spot поддерживает stoploss on exchange с market/limit stop orders. В dry-run это симулируется, реальные ордера на биржу не отправляются.

## Чеклист перед мыслями о реальных деньгах

- `dry_run` ни разу не должен быть случайно выключен.
- Бэктест должен быть прибыльным не только на одном коротком периоде.
- Сделок должно быть достаточно, обычно больше 100-200 на проверяемый рынок.
- Out-of-sample период должен быть отдельно прибыльным или хотя бы не разваливаться.
- Max drawdown должен быть психологически и финансово приемлемым.
- Нужно проверить комиссии, проскальзывание и минимальные размеры ордеров.
- Нужно минимум несколько недель dry-run на живом рынке.
- API ключи должны быть без права вывода средств.
- Нельзя запускать стратегию, которая уже в бэктесте показывает стабильный минус.

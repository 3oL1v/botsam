# Crypto Trading Bot — Freqtrade (Bybit Futures, DRY-RUN) + Railway + Telegram Mini App

> Бумажная торговля (виртуальные деньги) на живых ценах Bybit. **Реальные деньги НЕ используются: `dry_run: true` везде и всегда.**
> Развёрнуто на Railway, мониторинг через Telegram Mini App.

---

## 🤖 ДЛЯ АГЕНТА (Codex/Claude): прочитай это первым

Контекст проекта, чтобы не повторять уже пройденные ошибки:

1. **Биржа — Bybit, режим futures.** Мы пришли к ней не сразу:
   - BingX spot — отказались (нет плеча/шортов, мало истории).
   - Binance futures — **не работает в облаке**: возвращает `451 restricted location` на IP дата-центров (включая Railway EU). VPN пользователя НЕ помогает, т.к. бот ходит к бирже с IP Railway, а не с компьютера.
   - **Bybit futures — РАБОТАЕТ на Railway.** На неё и переключились. НЕ переключай обратно на Binance для облачного деплоя.
2. **Локально (Windows, домашний IP пользователя) биржи геоблокированы** (Binance 451, Bybit 403 CloudFront). Поэтому `download-data`/`backtesting`/`trade` локально по Bybit/Binance **упадут**. Проверять биржевые вещи нужно по **логам Railway**, а не локально.
3. **Это dry-run.** Никогда не ставь `dry_run: false`. Реальные ключи не нужны (публичные цены идут без ключей).
4. **Деплой только через git push** в `https://github.com/3oL1v/botsam.git` → Railway сам пересобирает.
5. **Windows-нюанс:** конфиги читаются системной кодировкой cp1251 → в `*.json` **только ASCII-комментарии** (без кириллицы), иначе `UnicodeDecodeError`. В `*.py` кириллица ок.
6. **Образ freqtrade ставит зависимости в `~/.local` пользователя `ftuser`.** В Dockerfile работаем как `ftuser` (НЕ root), иначе `No module named uvicorn`.

---

## 📊 Что развёрнуто (актуально)

| Параметр | Значение |
|---|---|
| Биржа | **bybit**, futures, isolated margin |
| Стратегия | `BinanceFuturesAtrStrategy` (имя историческое, работает на Bybit) |
| Депозит (dry-run) | **100 USDT** виртуальных |
| Плечо | до **50x** (`min(50, max биржи)`) |
| Размер позиции | постоянный **нотионал 100 USDT** → маржа = 100/плечо (при 50x = 2 USDT) |
| Стоп-лосс | `min(2*ATR, 1% цены)` — узкий, чтобы выйти ДО ликвидации при 50x |
| Тейк-профит | R:R = 1:1.5 (с учётом плеча) |
| Пары | 10 шт.: BTC, ETH, SOL, BNB, XRP, TON, DOGE, LINK, ADA, AVAX (формат `BTC/USDT:USDT`) |
| Таймфрейм | 1h |
| Хостинг | Railway (регион EU), Docker |
| Мониторинг | Telegram Mini App (@z3lv_bot) + web dashboard |

---

## 🗂️ Структура проекта

| Что | Путь |
|---|---|
| **Активный конфиг** (Bybit futures) | `user_data/config_binance_futures_dry.json` |
| **Активная стратегия** | `user_data/strategies/binance_futures_atr_strategy.py` |
| Старый конфиг (spot, не используется в деплое) | `user_data/config.json` |
| Старая стратегия (spot long-only) | `user_data/strategies/atr_trend_strategy.py` |
| Dashboard + Mini App (FastAPI) | `dashboard/server.py`, `dashboard/static/` |
| Деплой | `Dockerfile`, `start.sh`, `railway.json`, `.dockerignore` |
| Секреты (НЕ в git) | `.env` |

---

## 🚀 Деплой на Railway

Архитектура контейнера (`start.sh`):
- **Dashboard/miniapp** слушает публичный `$PORT` (Railway задаёт его сам) — поднимается СРАЗУ.
- **Бот freqtrade** работает в фоне на `127.0.0.1:8081` (внутренний) с авто-перезапуском.
- Если бот падает — dashboard остаётся жив и показывает статус.

### Переменные окружения на Railway (Variables)
| Переменная | Зачем |
|---|---|
| `MINIAPP_ACCESS_TOKEN` | токен доступа к Mini App. URL: `.../miniapp?access=ЭТОТ_ТОКЕН` |
| `PORT` | задаётся Railway автоматически, трогать не нужно |

> Внутренние креды freqUI (jwt/password) в конфиге — заглушки `LOCAL_INTERNAL_ONLY_*`, т.к. порт 8081 не публичный. При желании можно переопределить через env `FREQTRADE__API_SERVER__*`.

### Как задеплоить изменения
```powershell
cd C:\trade2
git add -A
git commit -m "описание"
git push
```
Railway увидит push и пересоберётся сам (~2-3 мин). Смотри вкладку **Deployments** и **Deploy Logs**.

### Текущий публичный URL
```
https://botsam-production.up.railway.app/miniapp?access=<MINIAPP_ACCESS_TOKEN>
```

---

## 📱 Telegram Mini App

Уже привязан к боту **@z3lv_bot**. Открывается кнопкой в Telegram на телефоне.

Чтобы привязать заново / к другому боту:
1. Telegram → @BotFather → `/newapp` (или `/myapps`).
2. Выбрать бота.
3. Указать Web App URL: публичный URL выше (с `?access=...`).
4. Mini App откроется кнопкой в чате бота.

Страница read-only: показывает статус, баланс, P/L, открытые/закрытые сделки, цену, RSI, Fear&Greed, funding. **Торговые команды НЕ отправляет.**

---

## ⚙️ Как менять параметры

### Размер позиции / плечо / стоп (в стратегии)
Файл `user_data/strategies/binance_futures_atr_strategy.py`, блок параметров:
```python
target_leverage = 50.0   # целевое плечо (берётся min с лимитом биржи)
target_notional = 100.0  # ПОСТОЯННАЯ стоимость позиции в USDT; маржа = notional/плечо
max_stop_pct = 0.01      # макс. ширина стопа = 1% цены (защита от ликвидации при 50x)
atr_multiplier = 2.0     # стоп = min(2*ATR, max_stop_pct)
risk_reward = 1.5        # тейк = 1.5 * риск
ema_fast = 50; ema_slow = 200
rsi_period = 14; rsi_long_entry = 35; rsi_long_exit = 70
rsi_short_entry = 65; rsi_short_exit = 30
```

### Депозит / пары / таймфрейм (в конфиге)
Файл `user_data/config_binance_futures_dry.json`:
- `dry_run_wallet` — виртуальный депозит (сейчас 100).
- `exchange.pair_whitelist` — список пар (формат `BTC/USDT:USDT`).
- `timeframe` — таймфрейм.
- `max_open_trades` — макс. одновременных сделок.

После правок: `git commit` + `git push` → Railway пересоберётся.

---

## ⚠️ РЕЗУЛЬТАТЫ БЭКТЕСТА — стратегия УБЫТОЧНА

Тестировалось на истории (Binance futures, 1h, до перехода на Bybit):

| Конфигурация | Итог | Profit factor | Прим. |
|---|---|---|---|
| Плечо 1x (исходно) | −39% за 2 года | 0.82 | без преимущества |
| **Плечо 50x, стоп 1%** | **−99.9%** | 0.75-0.83 | при 50x каждый стоп = −50% депозита |

**Честный вывод:** стратегия НЕ оверфитнута, инфраструктура работает идеально, но **торгового преимущества у стратегии нет — она теряет деньги**. При 50x плече слив депозита почти гарантирован математически (1% движения цены = 50% депозита). Out-of-sample (ранний/поздний период) одинаково убыточен.

Dry-run запущен для проверки инфраструктуры и наблюдения, **НЕ ради прибыли.**

---

## ✅ Чеклист ПЕРЕД мыслями о реальных деньгах

Реальная торговля = `dry_run: false`. **НЕ делай, пока не выполнено ВСЁ:**

- [ ] Стратегия **прибыльна** в бэктесте (Profit factor > 1.3). *(Сейчас ~0.8 — НЕ выполнено.)*
- [ ] Out-of-sample подтверждает прибыль.
- [ ] Макс. просадка приемлема (< 20-25%). *(Сейчас катастрофа при 50x — НЕ выполнено.)*
- [ ] Плечо снижено до разумного. *(50x = ликвидация при 2% — крайне опасно.)*
- [ ] Несколько недель стабильного dry-run на живом рынке.
- [ ] API-ключи Bybit: только Read + Trade, БЕЗ Withdraw.
- [ ] Готов потерять вложенное полностью.

> Сейчас выполнены НЕ все пункты: **реальная торговля противопоказана.**

---

## 🔧 Частые проблемы

| Симптом | Причина / решение |
|---|---|
| `451 restricted location` | биржа блокирует облачный IP. Это было с Binance → перешли на Bybit. |
| `403 CloudFront ... block access from your country` | геоблок IP. На локальной машине пользователя биржи заблокированы — проверяй через Railway. |
| `No module named uvicorn` | работали как root вместо ftuser. В Dockerfile должно быть `USER ftuser`. |
| `Application failed to respond` (Railway) | dashboard не привязал `$PORT`. start.sh должен поднимать dashboard СРАЗУ (foreground), бота — в фоне. |
| miniapp: `HTTPConnectionPool 127.0.0.1:8081` | бот ещё грузится или упал. Подожди ~1 мин / смотри логи. |
| `UnicodeDecodeError` при чтении конфига | кириллица в `*.json`. Убери — только ASCII-комментарии. |

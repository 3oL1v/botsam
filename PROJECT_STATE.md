# PROJECT_STATE.md — память проекта (читать ПЕРВЫМ, не перечитывать весь чат)

> Назначение: краткая «правда о проекте», чтобы агент (Claude/Codex) быстро вошёл в контекст
> без перечитывания всей истории. Обновлять при каждом значимом изменении.
> Последнее обновление: 2026-06-02.

---

## 1. ЧТО ЭТО
Крипто-торговый бот на **Freqtrade 2026.5**, режим **только dry-run** (бумажная торговля,
виртуальные деньги, `dry_run: true` всегда). Развёрнут на **Railway** (Docker), мониторинг —
**Telegram Mini App** (@z3lv_bot) + web dashboard. GitHub: https://github.com/3oL1v/botsam

## 2. ТЕКУЩИЙ СТАТУС (на 2026-06-02)
- ✅ Код, Dockerfile, dashboard/miniapp, Telegram-уведомления — готовы и в репо.
- ✅ Деплой на Railway собирается, контейнер стартует, dashboard/miniapp отвечает.
- 🔴 **ГЛАВНЫЙ БЛОКЕР: биржа недоступна с IP Railway.**
  - Binance → `451 restricted location`.
  - Bybit → `403 CloudFront ... block access from your country`.
  - Бот не может загрузить рынки → не торгует (баланс показывает, но сделок нет).
- ⏳ **СЛЕДУЮЩИЙ ШАГ (выбран пользователем): сменить РЕГИОН Railway** на Singapore
  (Southeast Asia), т.к. Bybit — азиатская биржа. Делает пользователь в панели Railway
  (Settings → Regions), у агента доступа к Railway НЕТ. После — прислать логи.
  - Если регион не поможет → fallback: прокси внутри контейнера (ccxt httpsProxy) или
    другая биржа (OKX/Gate/MEXC/Kraken).

## 3. КЛЮЧЕВЫЕ ФАКТЫ / ГРАБЛИ (НЕ повторять ошибки)
1. **Биржа сейчас = Bybit, futures.** (Файл стратегии назван binance-historically, это ок.)
2. **451/403 происходят на стороне Railway, НЕ на компе.** VPN пользователя на это НЕ влияет —
   бот ходит к бирже с IP Railway. Лечится сменой региона/прокси/биржи, а НЕ VPN.
3. **Локально (домашний IP пользователя) биржи тоже заблокированы** → `download-data`,
   `backtesting`, `trade` локально по Binance/Bybit ПАДАЮТ. Проверять только через логи Railway.
4. **Windows cp1251:** в `*.json` только ASCII-комментарии (иначе UnicodeDecodeError). В `*.py` кириллица ок.
5. **Docker:** базовый образ freqtrade ставит зависимости в `~/.local` юзера `ftuser`.
   В Dockerfile работать как `USER ftuser` (НЕ root), иначе `No module named uvicorn`.
6. **start.sh:** dashboard поднимается СРАЗУ на `$PORT` (foreground), бот — в фоне с авто-рестартом.
   Иначе Railway даёт "Application failed to respond".
7. **Деплой = git push** → Railway пересобирает сам.
8. **Локально не запускать бота** (геоблок) — только редактируем код и пушим.

## 4. НАСТРОЙКИ ТОРГОВЛИ (по запросу пользователя)
- Депозит (dry-run): **100 USDT** (`dry_run_wallet` в config_binance_futures_dry.json).
- Плечо: до **50x** (`target_leverage` в стратегии, min с лимитом биржи).
- Размер позиции: постоянный **нотионал 100 USDT** → маржа = 100/плечо (при 50x = 2 USDT).
- Стоп: `min(2*ATR, 1% цены)` (`max_stop_pct=0.01`) — узкий, чтобы выйти до ликвидации при 50x.
- Тейк: R:R 1.5. Пары: 10 шт futures (BTC/ETH/SOL/BNB/XRP/TON/DOGE/LINK/ADA/AVAX), TF 1h.
- ⚠️ Бэктест убыточен (PF ~0.8; при 50x ~−100%). Это для наблюдения, НЕ для заработка.

## 5. СТРУКТУРА (что где)
| Что | Путь |
|---|---|
| **Активный конфиг** | `user_data/config_binance_futures_dry.json` |
| **Активная стратегия** | `user_data/strategies/binance_futures_atr_strategy.py` |
| Старый spot-конфиг (не в деплое) | `user_data/config.json` |
| Старая spot-стратегия | `user_data/strategies/atr_trend_strategy.py` |
| Dashboard + Mini App | `dashboard/server.py`, `dashboard/static/` |
| Деплой | `Dockerfile`, `start.sh`, `railway.json`, `.dockerignore` |
| Доки | `README_RU.md` (общая), `DEPLOY_RAILWAY_RU.md` (пошаговый деплой), этот файл |
| Секреты (НЕ в git) | `.env` |

## 6. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ Railway (Variables)
| Переменная | Назначение |
|---|---|
| `MINIAPP_ACCESS_TOKEN` | доступ к Mini App: `/miniapp?access=ТОКЕН` |
| `FREQTRADE__TELEGRAM__TOKEN` | токен Telegram-бота (@BotFather) — для уведомлений |
| `FREQTRADE__TELEGRAM__CHAT_ID` | chat_id пользователя (@userinfobot) |
| `PORT` | задаёт Railway автоматически |
> ⚠️ telegram.enabled=true в конфиге → без TOKEN и CHAT_ID бот упадёт при старте.

## 7. ИСТОРИЯ РЕШЕНИЙ (кратко)
- Старт: BingX spot → отказ (нет плеча/шортов, мало истории, у BingX ~1 год 1h).
- Перешли на Binance futures (2 года данных) → бэктест убыточен, но инфра работала.
- Пользователь: депозит 100, плечо 50, нотионал 100 → применено; бэктест ~−100% (плечо губит).
- Деплой Railway: чинили по очереди — "failed to respond" (start.sh), "No module uvicorn"
  (ftuser), затем Binance 451 → переключили на Bybit → Bybit 403 на Railway тоже.
- Сейчас: пробуем сменить регион Railway на Singapore.

## 8. ЧЕКЛИСТ ПЕРЕД РЕАЛЬНЫМИ ДЕНЬГАМИ
Не включать реал (`dry_run:false`), пока: PF>1.3 в бэктесте + out-of-sample прибылен +
просадка <20-25% + плечо снижено + недели стабильного dry-run + ключи без Withdraw.
Сейчас НЕ выполнено — реал противопоказан.

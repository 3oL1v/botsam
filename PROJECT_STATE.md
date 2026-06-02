# PROJECT_STATE.md — память проекта (читать ПЕРВЫМ, не перечитывать весь чат)

> Назначение: краткая «правда о проекте», чтобы агент (Claude/Codex) быстро вошёл в контекст
> без перечитывания всей истории. Обновлять при каждом значимом изменении.
> Последнее обновление: 2026-06-02.

---

## 1. ЧТО ЭТО
Крипто-торговый бот на **Freqtrade 2026.5**, режим **только dry-run** (бумажная торговля,
виртуальные деньги, `dry_run: true` всегда). Развёрнут на **Railway** (Docker), мониторинг —
**Telegram Mini App** (@z3lv_bot) + web dashboard. GitHub: https://github.com/3oL1v/botsam

**Биржа: BINANCE futures** (вернулись с Bybit, т.к. регион Singapore решил блок; Binance крупнее).
**Telegram-уведомления: на РУССКОМ** — слются из стратегии через `self.dp.send_msg()` в колбэке
`order_filled` (вход/выход + результат). Встроенные англ. уведомления Freqtrade ОТКЛЮЧЕНЫ
(entry/exit/*=off), чтобы не было дублей; включены `allow_custom_messages` + `strategy_msg=on`.
> У Freqtrade НЕТ встроенной локализации — русский только через send_msg в order_filled.

## 2. ТЕКУЩИЙ СТАТУС (на 2026-06-02, обновлено)
- ✅ Код, Dockerfile, dashboard/miniapp, Telegram-уведомления — готовы и в репо.
- ✅ Деплой на Railway собирается, контейнер стартует, dashboard/miniapp отвечает.
- ✅ **БИРЖЕВОЙ БЛОКЕР РЕШЁН: смена региона Railway на Singapore сработала.**
  Bybit с Singapore отдаёт данные (`leverage_tiers_USDT.json` загружается, `Wallets synced`).
  Никаких 403/451. ВАЖНО: держать регион Railway = Southeast Asia (Singapore).
- ⏳ **ПОСЛЕДНИЙ ШАГ: пользователь добавляет в Railway Variables**
  `FREQTRADE__TELEGRAM__TOKEN` (от @BotFather, бот @z3lv_bot) и
  `FREQTRADE__TELEGRAM__CHAT_ID` (от @userinfobot). Без них бот падает с
  `InvalidToken` (т.к. telegram.enabled=true). После — Redeploy и `/start` боту.
  - Если не хочет Telegram — поставить telegram.enabled=false в конфиге.

## 2b. ТЕСТ РАБОТОСПОСОБНОСТИ БОТА
- Сигнал входа РЕДКИЙ (RSI cross 35 в аптренде) — 0 сделок за часы это НОРМА, не баг.
- `force_entry_enable: true` включён → в Telegram доступны `/forcelong`, `/forceshort`.
- Проверка: `/forcelong BTC/USDT:USDT` открывает сделку сразу. `/status` /`/count` — бот жив.
- **Inline-кнопки Telegram (Which pair/Which trade) часто не нажимаются** (устаревают при
  рестарте контейнера). Решение: вводить команду с аргументом — `/forcelong BTC/USDT:USDT`,
  `/forceexit <id>` (id виден в /status, напр. 1).
- БАГ (история фиксов order_filled — определение вход/выход):
  1) было `order.ft_order_side=="enter"` — НИКОГДА не истинно (поле = buy/sell) → ложный "выход".
  2) пробовал `order.ft_is_entry` — у Order НЕТ такого атрибута → AttributeError/краш.
  3) ПРАВИЛЬНО (из доков): `if order.ft_order_side == trade.entry_side:` = вход, иначе выход.
- ВАЖНО про /forcelong: ордер ЛИМИТНЫЙ, в dry-run исполняется не мгновенно (~20-40 сек).
  Если сразу сделать /forceexit — отменишь ордер ДО исполнения ("forcesold, fully cancelled").
  Надо подождать заполнения (в логах "LIMIT_BUY has been fulfilled"), потом /forceexit <id>.
- Telegram: встроенные уведомления (entry/exit/...) ВЫКЛЮЧЕНЫ, шлём только свои русские через
  send_msg. Для этого в конфиге allow_custom_messages=true и notification_settings.strategy_msg=on.

## 2c. УПРАВЛЕНИЕ ЧЕРЕЗ MINI APP (вместо нестабильных Telegram-кнопок)
- Telegram inline-кнопки (Which pair/trade) протухают при рестартах — отказались от них.
  Нижняя клавиатура Telegram не годится: forcelong/forceexit туда нельзя (нет в allowed list).
- РЕШЕНИЕ: вкладка "Управление" в Mini App. Файлы: dashboard/static/miniapp.{html,js,css}.
  Backend dashboard/server.py проксирует в Freqtrade REST:
    POST /api/control/forceenter {pair, side}  -> freqtrade POST /forceenter (ordertype=market)
    POST /api/control/forceexit  {tradeid}      -> freqtrade POST /forceexit  (ordertype=market)
  Оба защищены MINIAPP_ACCESS_TOKEN (заголовок X-Miniapp-Token или ?access=).
  ВАЖНО: управление использует require_control_access — если MINIAPP_ACCESS_TOKEN на
  сервере НЕ задан, управление ЗАПРЕЩЕНО (403). Просмотр (require_miniapp_access) при
  пустом токене открыт. Поэтому MINIAPP_ACCESS_TOKEN ОБЯЗАТЕЛЬНО задать в Railway Variables,
  иначе кнопки Лонг/Шорт/Закрыть вернут 403. (Баг был: токен не задан -> управление открыто всем.)
  Побочно: чтение body ДО проверки токена убирает ложный 502 на прокси Railway.
- Вход через Mini App = МARKET ордер (исполняется сразу, без задержки лимитника).
- Кнопки: Лонг/Шорт + выбор пары; список открытых сделок с кнопкой "Закрыть #id".

## 3. КЛЮЧЕВЫЕ ФАКТЫ / ГРАБЛИ (НЕ повторять ошибки)
1. **Биржа сейчас = Binance, futures.** Работает на Railway ТОЛЬКО из региона Singapore.
   НЕ менять регион Railway с Singapore — иначе вернётся 451/403.
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

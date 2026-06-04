# Project State

Last updated: 2026-06-04.

## Current Runtime

- Platform: local Windows now; Railway deploy prepared.
- Exchange: Binance USD-M Futures.
- Mode: dry-run only.
- Margin mode: isolated.
- Wallet: 100 virtual USDT per bot.
- Public service: Mini App dashboard only.
- Internal Freqtrade APIs: `127.0.0.1:8081`, `127.0.0.1:8082`, `127.0.0.1:8083`.

## Active Bots

| Bot | Config | Strategy | API |
|---|---|---|---|
| volatility | `user_data/config_volatility_dry.json` | `VolatilitySqueezeBreakoutAggressive` | `8081` |
| donchian | `user_data/config_donchian_dry.json` | `DonchianVolumeBurst5m` | `8082` |
| vwap | `user_data/config_vwap_dry.json` | `VWAPPullbackMomentumScalp` | `8083` |

All active configs must keep `"dry_run": true`.

## Dashboard

- Backend: `dashboard/server.py`.
- UI: `dashboard/static/miniapp.html`, `miniapp.css`, `miniapp.js`.
- Local URL: `http://127.0.0.1:8092/miniapp?access=...`.
- Journal DB: `dashboard/data/trade_journal.sqlite`.
- Journal records strategy, bot, pair, side, open/close data, PnL and a strategy parameter snapshot.

## Railway

- Dockerfile uses `freqtradeorg/freqtrade:stable`.
- `start.sh` supports `SERVICE_ROLE=all|dashboard|volatility|donchian|vwap`.
- Recommended production layout: 4 Railway services in one project.
- Dashboard service should expose only `$PORT` publicly.
- Bot services should set `PORT=8080` and do not need public domains.
- Set `MINIAPP_ACCESS_TOKEN` in Railway Variables.
- Binance may reject cloud IPs with HTTP 451. Check deploy logs and `/api/health`.
- Token-protected log tails are available at `/api/logs?name=donchian&access=...`.

Dashboard service variables for private networking:

```text
BOT_VOLATILITY_URL=http://volatility.railway.internal:8080/api/v1
BOT_DONCHIAN_URL=http://donchian.railway.internal:8080/api/v1
BOT_VWAP_URL=http://vwap.railway.internal:8080/api/v1
```

## Commands

```powershell
.\run_dryrun.ps1
.\run_https_tunnel.ps1
.\stop_dryrun_stack.ps1
```

Railway CLI after login/link:

```powershell
railway variables set MINIAPP_ACCESS_TOKEN="..."
railway up
railway logs
```

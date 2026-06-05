---
title: Freqtrade Dry-Run Dashboard
emoji: 📊
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8092
pinned: false
---

# Freqtrade Dry-Run Stack (Bybit) + Telegram Mini App

Paper-trading only. All bot configs run with `dry_run: true` — **no real money, no real orders**.
This Space runs 3 Freqtrade dry-run bots (Bybit USDⓈ-M futures) plus a Mini App
dashboard that aggregates them, all in one container (`SERVICE_ROLE=all`).

## Hugging Face deployment notes

- **SDK:** Docker. The container starts `start.sh`, which launches the 3 bots
  (internal ports 8081/8082/8083) and the dashboard on `app_port` (8092).
- **Secret:** set `MINIAPP_ACCESS_TOKEN` in *Settings → Variables and secrets*.
  The dashboard is reachable at `/miniapp?access=<MINIAPP_ACCESS_TOKEN>`.
- **Keep-alive:** the free CPU tier sleeps after 48h without traffic. A GitHub
  Actions workflow (`.github/workflows/keepalive.yml`) pings the Space every 6h.

See `README_RU.md` for the full Russian documentation and `research/` (not in the
image) for the honest backtest that found all three strategies unprofitable.

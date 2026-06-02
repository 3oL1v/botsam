from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

import ccxt
import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from requests.auth import HTTPBasicAuth


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("DASHBOARD_CONFIG", "user_data/config.json"))
if not CONFIG_PATH.is_absolute():
    CONFIG_PATH = ROOT / CONFIG_PATH
STATIC_DIR = Path(__file__).resolve().parent / "static"

MARKET_TTL = 8
FNG_TTL = 60 * 20
BOT_TTL = 5
MINIAPP_TTL = 5
def env_setting(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


MINIAPP_ACCESS_TOKEN = env_setting("MINIAPP_ACCESS_TOKEN")

app = FastAPI(title="Dry Market Dashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_cache: dict[str, tuple[float, Any]] = {}
_exchange_clients: dict[str, Any] = {}


def _now() -> float:
    return time.time()


def _cached(key: str, ttl: int, loader):
    item = _cache.get(key)
    if item and _now() - item[0] < ttl:
        return item[1]
    value = loader()
    _cache[key] = (_now(), value)
    return value


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def market_context() -> dict[str, Any]:
    config = load_config()
    exchange = config.get("exchange", {})
    return {
        "exchange": exchange.get("name", "unknown"),
        "trading_mode": config.get("trading_mode", "spot"),
        "timeframe": config.get("timeframe", "1h"),
        "stake_currency": config.get("stake_currency", "USDT"),
        "config": str(CONFIG_PATH),
        "dry_run": config.get("dry_run") is True,
    }


def configured_pairs() -> list[str]:
    config = load_config()
    return list(config["exchange"]["pair_whitelist"])


def _merged_ccxt_config(default_type: str | None = None) -> dict[str, Any]:
    config = load_config()
    exchange_config = config.get("exchange", {})
    raw = exchange_config.get("ccxt_config", {})
    merged: dict[str, Any] = {"timeout": 15000, "enableRateLimit": True}
    if isinstance(raw, dict):
        merged.update({key: value for key, value in raw.items() if key != "options"})
    options = dict(raw.get("options", {}) if isinstance(raw, dict) else {})
    if default_type:
        options["defaultType"] = default_type
    if options:
        merged["options"] = options
    return merged


def exchange_client(kind: str = "market"):
    context = market_context()
    exchange_name = context["exchange"]
    trading_mode = context["trading_mode"]
    default_type = "swap" if trading_mode == "futures" or kind == "funding" else "spot"
    cache_key = f"{exchange_name}:{default_type}:{kind}:{CONFIG_PATH}"

    if cache_key not in _exchange_clients:
        exchange_class = getattr(ccxt, exchange_name)
        _exchange_clients[cache_key] = exchange_class(_merged_ccxt_config(default_type))

    return _exchange_clients[cache_key]


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except Exception:
        return None


def round_opt(value: Any, digits: int = 8) -> float | None:
    number = safe_float(value)
    return None if number is None else round(number, digits)


def calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    if len(closes) <= period:
        return [None for _ in closes]

    values: list[float | None] = [None for _ in closes]
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, period + 1)]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    values[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        values[i] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    return values


def normalize_orderbook(entries: list[list[float]], depth: int) -> list[dict[str, float]]:
    rows = []
    total = 0.0
    for price, amount, *_ in entries[:depth]:
        total += float(amount)
        rows.append(
            {
                "price": float(price),
                "amount": float(amount),
                "total": total,
            }
        )
    return rows


def funding_symbol(pair: str) -> str:
    if ":" in pair:
        return pair
    base = pair.split("/")[0]
    quote = pair.split("/")[1].split(":")[0] if "/" in pair else "USDT"
    if base == "TONCOIN":
        base = "TON"
    return f"{base}/{quote}:{quote}"


def fetch_funding(pair: str) -> dict[str, Any]:
    symbol = funding_symbol(pair)
    context = market_context()
    try:
        data = exchange_client("funding").fetch_funding_rate(symbol)
        rate = safe_float(data.get("fundingRate"))
        return {
            "symbol": symbol,
            "rate": rate,
            "percent": None if rate is None else round(rate * 100, 5),
            "datetime": data.get("datetime"),
            "source": f"{context['exchange']} perpetual public data",
            "available": True,
        }
    except Exception as exc:
        return {
            "symbol": symbol,
            "rate": None,
            "percent": None,
            "datetime": None,
            "source": f"{context['exchange']} perpetual public data",
            "available": False,
            "error": str(exc)[:180],
        }


def fetch_fear_greed() -> dict[str, Any]:
    def loader():
        try:
            response = requests.get("https://api.alternative.me/fng/?limit=1", timeout=15)
            response.raise_for_status()
            row = response.json()["data"][0]
            return {
                "value": int(row["value"]),
                "classification": row["value_classification"],
                "timestamp": int(row["timestamp"]),
                "available": True,
            }
        except Exception as exc:
            return {"value": None, "classification": "Unavailable", "available": False, "error": str(exc)[:180]}

    return _cached("fear_greed", FNG_TTL, loader)


def fetch_bot_state() -> dict[str, Any]:
    def loader():
        config = load_config()
        api_config = config.get("api_server", {})
        base_url = f"http://{api_config.get('listen_ip_address', '127.0.0.1')}:{api_config.get('listen_port', 8080)}"
        username = api_config.get("username", "")
        password = api_config.get("password", "")
        state: dict[str, Any] = {
            "dry_run": config.get("dry_run") is True,
            "trading_mode": config.get("trading_mode"),
            "timeframe": config.get("timeframe"),
            "exchange": config.get("exchange", {}).get("name"),
            "pairs": configured_pairs(),
            "freqtrade_api": base_url,
            "available": False,
        }
        try:
            token_response = requests.post(
                f"{base_url}/api/v1/token/login",
                auth=HTTPBasicAuth(username, password),
                timeout=5,
            )
            token_response.raise_for_status()
            token = token_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            count = requests.get(f"{base_url}/api/v1/count", headers=headers, timeout=5).json()
            profit = requests.get(f"{base_url}/api/v1/profit", headers=headers, timeout=5).json()
            state.update(
                {
                    "available": True,
                    "open_trades": count.get("current", 0),
                    "max_open_trades": count.get("max", 0),
                    "total_stake": count.get("total_stake", 0),
                    "trade_count": profit.get("trade_count", 0),
                    "closed_trade_count": profit.get("closed_trade_count", 0),
                    "profit_all_percent": profit.get("profit_all_percent", 0),
                    "profit_all_coin": profit.get("profit_all_coin", 0),
                    "winrate": profit.get("winrate", 0),
                }
            )
        except Exception as exc:
            state["error"] = str(exc)[:180]
        return state

    return _cached("bot_state", BOT_TTL, loader)


def _freqtrade_api_base() -> tuple[str, str, str]:
    config = load_config()
    api_config = config.get("api_server", {})
    base_url = f"http://{api_config.get('listen_ip_address', '127.0.0.1')}:{api_config.get('listen_port', 8080)}"
    return base_url, api_config.get("username", ""), api_config.get("password", "")


def _freqtrade_token() -> str:
    base_url, username, password = _freqtrade_api_base()
    response = requests.post(
        f"{base_url}/api/v1/token/login",
        auth=HTTPBasicAuth(username, password),
        timeout=5,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def freqtrade_api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    base_url, _, _ = _freqtrade_api_base()
    token = _freqtrade_token()
    response = requests.get(
        f"{base_url}/api/v1/{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=8,
    )
    response.raise_for_status()
    return response.json()


def freqtrade_api_post(path: str, payload: dict[str, Any]) -> Any:
    """POST в Freqtrade REST API (для forceenter/forceexit)."""
    base_url, _, _ = _freqtrade_api_base()
    token = _freqtrade_token()
    response = requests.post(
        f"{base_url}/api/v1/{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=15,
    )
    # пробрасываем тело ошибки, чтобы показать причину в Mini App
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = {"error": response.text[:200]}
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


def _profit_percent(trade: dict[str, Any]) -> float | None:
    for key in ("profit_pct", "close_profit_pct", "profit_percent", "close_profit_percent"):
        value = safe_float(trade.get(key))
        if value is not None:
            return value
    for key in ("profit_ratio", "close_profit", "close_profit_ratio"):
        value = safe_float(trade.get(key))
        if value is not None:
            return value * 100
    return None


def normalize_trade(trade: dict[str, Any]) -> dict[str, Any]:
    pair = trade.get("pair") or trade.get("symbol") or "-"
    is_short = bool(trade.get("is_short"))
    profit_abs = safe_float(
        trade.get("profit_abs")
        if trade.get("profit_abs") is not None
        else trade.get("close_profit_abs")
        if trade.get("close_profit_abs") is not None
        else trade.get("realized_profit")
    )
    return {
        "id": trade.get("trade_id") or trade.get("id"),
        "pair": pair,
        "side": "SHORT" if is_short else "LONG",
        "is_short": is_short,
        "is_open": bool(trade.get("is_open", trade.get("close_date") is None)),
        "stake_amount": round_opt(trade.get("stake_amount"), 4),
        "amount": round_opt(trade.get("amount"), 8),
        "open_rate": round_opt(trade.get("open_rate"), 8),
        "current_rate": round_opt(trade.get("current_rate"), 8),
        "close_rate": round_opt(trade.get("close_rate"), 8),
        "profit_percent": round_opt(_profit_percent(trade), 4),
        "profit_abs": round_opt(profit_abs, 4),
        "leverage": round_opt(trade.get("leverage"), 2),
        "open_date": trade.get("open_date") or trade.get("open_date_hum"),
        "close_date": trade.get("close_date") or trade.get("close_date_hum"),
        "duration": trade.get("trade_duration") or trade.get("duration"),
        "exit_reason": trade.get("exit_reason") or trade.get("sell_reason"),
        "entry_tag": trade.get("enter_tag") or trade.get("entry_tag"),
    }


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.get("trades", []))
    return []


def fetch_miniapp(pair: str | None = None) -> dict[str, Any]:
    selected_pair = pair if pair in configured_pairs() else configured_pairs()[0]
    cache_key = f"miniapp:{selected_pair}"

    def loader():
        context = market_context()
        bot = fetch_bot_state()
        errors: list[str] = []

        status: Any = []
        trades_response: Any = {"trades": []}
        profit: dict[str, Any] = {}
        count: dict[str, Any] = {}
        balance: dict[str, Any] = {}
        show_config: dict[str, Any] = {}
        performance: Any = []

        for name, path, params in (
            ("status", "status", None),
            ("trades", "trades", {"limit": 20, "offset": 0}),
            ("profit", "profit", None),
            ("count", "count", None),
            ("balance", "balance", None),
            ("show_config", "show_config", None),
            ("performance", "performance", None),
        ):
            try:
                value = freqtrade_api_get(path, params)
                if name == "status":
                    status = value
                elif name == "trades":
                    trades_response = value
                elif name == "profit":
                    profit = value
                elif name == "count":
                    count = value
                elif name == "balance":
                    balance = value
                elif name == "show_config":
                    show_config = value
                elif name == "performance":
                    performance = value
            except Exception as exc:
                errors.append(f"{name}: {str(exc)[:120]}")

        market: dict[str, Any] | None = None
        try:
            full_market = fetch_market(selected_pair)
            market = {
                "pair": selected_pair,
                "last": full_market.get("ticker", {}).get("last"),
                "change24h": full_market.get("ticker", {}).get("percentage"),
                "rsi": full_market.get("rsi"),
                "funding": full_market.get("funding"),
                "fear_greed": full_market.get("fear_greed"),
                "chart": full_market.get("chart", [])[-48:],
            }
        except Exception as exc:
            errors.append(f"market: {str(exc)[:120]}")

        open_trades = [normalize_trade(item) for item in _as_list(status)]
        recent_trades = [normalize_trade(item) for item in _as_list(trades_response)]
        closed_trades = [item for item in recent_trades if not item["is_open"]]
        currencies = balance.get("currencies", []) if isinstance(balance, dict) else []
        stake_row = next((item for item in currencies if item.get("currency") == context.get("stake_currency")), None)
        if stake_row is None and currencies:
            stake_row = currencies[0]

        return {
            "context": {
                **context,
                "bot_name": show_config.get("bot_name"),
                "strategy": show_config.get("strategy"),
                "short_allowed": show_config.get("short_allowed"),
                "max_open_trades": show_config.get("max_open_trades"),
            },
            "summary": {
                "available": bot.get("available", False),
                "dry_run": context.get("dry_run"),
                "open_trades": count.get("current", bot.get("open_trades", len(open_trades))),
                "max_open_trades": count.get("max", bot.get("max_open_trades")),
                "total_stake": count.get("total_stake", 0),
                "trade_count": profit.get("trade_count", 0),
                "closed_trade_count": profit.get("closed_trade_count", 0),
                "profit_all_percent": profit.get("profit_all_percent", 0),
                "profit_all_coin": profit.get("profit_all_coin", 0),
                "profit_closed_coin": profit.get("profit_closed_coin", 0),
                "winrate": profit.get("winrate", 0),
                "balance_total": balance.get("total"),
                "balance_value": balance.get("value"),
                "stake_free": None if stake_row is None else stake_row.get("free"),
            },
            "open_trades": open_trades,
            "recent_trades": closed_trades[:12],
            "performance": _as_list(performance)[:8],
            "pairs": configured_pairs(),
            "market": market,
            "errors": errors,
            "updated_at": int(_now() * 1000),
        }

    return _cached(cache_key, MINIAPP_TTL, loader)


def require_miniapp_access(request: Request) -> None:
    # Просмотр: если токен на сервере НЕ задан — доступ открыт (read-only данные).
    if not MINIAPP_ACCESS_TOKEN:
        return
    supplied = request.headers.get("x-miniapp-token") or request.query_params.get("access")
    if supplied != MINIAPP_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Miniapp access token required")


def require_control_access(request: Request) -> None:
    """
    Управление (открыть/закрыть сделку) — строже просмотра:
    - если MINIAPP_ACCESS_TOKEN на сервере НЕ задан, управление ЗАПРЕЩЕНО полностью
      (защита по умолчанию: лучше не дать управлять, чем открыть всем);
    - если задан — требуем точное совпадение токена.
    """
    if not MINIAPP_ACCESS_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Управление отключено: на сервере не задан MINIAPP_ACCESS_TOKEN",
        )
    supplied = request.headers.get("x-miniapp-token") or request.query_params.get("access")
    if supplied != MINIAPP_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Нужен корректный токен доступа")


def fetch_market(pair: str) -> dict[str, Any]:
    if pair not in configured_pairs():
        raise ValueError(f"Pair {pair} is not in config whitelist")

    def loader():
        context = market_context()
        timeframe = context["timeframe"]
        market_exchange = exchange_client("market")
        ticker = market_exchange.fetch_ticker(pair)
        orderbook = market_exchange.fetch_order_book(pair, limit=20)
        candles = market_exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=160)
        closes = [float(candle[4]) for candle in candles]
        rsi_values = calc_rsi(closes)
        chart = [
            {
                "time": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
                "rsi": None if rsi_values[index] is None else round(float(rsi_values[index]), 2),
            }
            for index, candle in enumerate(candles)
        ]

        bids = normalize_orderbook(orderbook.get("bids", []), 10)
        asks = normalize_orderbook(orderbook.get("asks", []), 10)
        best_bid = bids[0]["price"] if bids else None
        best_ask = asks[0]["price"] if asks else None
        spread = None
        if best_bid and best_ask:
            spread = best_ask - best_bid

        return {
            "pair": pair,
            "context": context,
            "ticker": {
                "last": round_opt(ticker.get("last")),
                "bid": round_opt(ticker.get("bid") if ticker.get("bid") is not None else best_bid),
                "ask": round_opt(ticker.get("ask") if ticker.get("ask") is not None else best_ask),
                "percentage": round_opt(ticker.get("percentage"), 3),
                "quoteVolume": round_opt(ticker.get("quoteVolume"), 2),
                "high": round_opt(ticker.get("high")),
                "low": round_opt(ticker.get("low")),
                "timestamp": ticker.get("timestamp"),
            },
            "orderbook": {
                "bids": bids,
                "asks": asks,
                "spread": round_opt(spread, 8),
            },
            "chart": chart,
            "rsi": chart[-1]["rsi"] if chart else None,
            "funding": fetch_funding(pair),
            "fear_greed": fetch_fear_greed(),
            "bot": fetch_bot_state(),
            "updated_at": int(_now() * 1000),
        }

    return _cached(f"market:{pair}", MARKET_TTL, loader)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/miniapp")
def miniapp():
    return FileResponse(STATIC_DIR / "miniapp.html")


@app.get("/api/pairs")
def api_pairs():
    return {
        "pairs": configured_pairs(),
        "context": market_context(),
        "bot": fetch_bot_state(),
        "fear_greed": fetch_fear_greed(),
    }


@app.get("/api/market")
def api_market(pair: str = Query(...)):
    try:
        return fetch_market(pair)
    except Exception as exc:
        return {"pair": pair, "available": False, "error": str(exc)[:240], "bot": fetch_bot_state()}


@app.get("/api/miniapp")
def api_miniapp(request: Request, pair: str | None = Query(default=None)):
    require_miniapp_access(request)
    try:
        return fetch_miniapp(pair)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc)[:240],
            "context": market_context(),
            "summary": fetch_bot_state(),
            "updated_at": int(_now() * 1000),
        }


# ---------------------------------------------------------------------------
#  УПРАВЛЕНИЕ из Mini App: открыть/закрыть сделку (только dry-run).
#  Проксируем в Freqtrade REST API. Защищено тем же miniapp-токеном.
# ---------------------------------------------------------------------------
@app.post("/api/control/forceenter")
async def api_force_enter(request: Request):
    # Сначала ЧИТАЕМ тело (иначе ответ до чтения body -> обрыв -> 502 на прокси),
    # затем проверяем токен -> чистый 401 при отсутствии доступа.
    try:
        body = await request.json()
    except Exception:
        body = {}
    require_control_access(request)
    pair = body.get("pair")
    side = body.get("side", "long")
    if pair not in configured_pairs():
        raise HTTPException(status_code=400, detail="Пара не в whitelist")
    if side not in ("long", "short"):
        raise HTTPException(status_code=400, detail="side должен быть long или short")
    # market — чтобы вход исполнялся сразу (удобно для теста)
    payload = {"pair": pair, "side": side, "ordertype": "market"}
    result = freqtrade_api_post("forceenter", payload)
    _cache.pop("bot_state", None)  # сбросить кэш статуса, чтобы UI сразу обновился
    return {"ok": True, "result": result}


@app.post("/api/control/forceexit")
async def api_force_exit(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    require_control_access(request)
    tradeid = body.get("tradeid")
    if tradeid in (None, ""):
        raise HTTPException(status_code=400, detail="Нужен tradeid (или 'all')")
    payload = {"tradeid": str(tradeid), "ordertype": "market"}
    result = freqtrade_api_post("forceexit", payload)
    _cache.pop("bot_state", None)
    return {"ok": True, "result": result}

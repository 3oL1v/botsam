from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(__file__).resolve().parent / "data"
JOURNAL_DB = DATA_DIR / "trade_journal.sqlite"
STRATEGY_DIR = ROOT / "user_data" / "strategies"

PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "BNB/USDT:USDT"]
MARKET_SYMBOLS = {
    "BTC/USDT:USDT": "BTCUSDT",
    "ETH/USDT:USDT": "ETHUSDT",
    "SOL/USDT:USDT": "SOLUSDT",
    "BNB/USDT:USDT": "BNBUSDT",
}

BOT_CONFIG_PATHS = [
    ROOT / "user_data" / "config_volatility_dry.json",
    ROOT / "user_data" / "config_donchian_dry.json",
    ROOT / "user_data" / "config_vwap_dry.json",
]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


ENV = load_env()
ACCESS_TOKEN = os.environ.get("MINIAPP_ACCESS_TOKEN") or ENV.get("MINIAPP_ACCESS_TOKEN", "")

app = FastAPI(title="Dry-Run Mini App", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_cache: dict[str, tuple[float, Any]] = {}


@dataclass(frozen=True)
class BotTarget:
    bot_id: str
    label: str
    config_path: Path
    base_url: str
    username: str
    password: str
    strategy: str
    port: int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def pick(data: dict[str, Any] | None, keys: list[str], default: Any = None) -> Any:
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def human_minutes(start: Any, end: Any | None = None) -> int | None:
    start_dt = parse_datetime(start)
    if not start_dt:
        return None
    end_dt = parse_datetime(end) or datetime.now(timezone.utc)
    return max(0, int((end_dt - start_dt).total_seconds() // 60))


def read_bot_targets() -> list[BotTarget]:
    targets: list[BotTarget] = []
    for config_path in BOT_CONFIG_PATHS:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        api = config["api_server"]
        strategy = config["strategy"]
        label = strategy.replace("VolatilitySqueezeBreakoutAggressive", "Volatility")
        label = label.replace("DonchianVolumeBurst5m", "Donchian")
        label = label.replace("VWAPPullbackMomentumScalp", "VWAP")
        port = int(api["listen_port"])
        targets.append(
            BotTarget(
                bot_id=str(config["bot_name"]),
                label=label,
                config_path=config_path,
                base_url=f"http://127.0.0.1:{port}/api/v1",
                username=str(api["username"]),
                password=str(api["password"]),
                strategy=strategy,
                port=port,
            )
        )
    return targets


def require_access(request: Request) -> None:
    if not ACCESS_TOKEN:
        return
    supplied = request.headers.get("x-miniapp-token") or request.query_params.get("access")
    if supplied != ACCESS_TOKEN:
        raise HTTPException(status_code=403, detail="Mini App access token is missing or invalid.")


def request_json(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> Any:
    response = requests.get(url, auth=auth, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def bot_get(bot: BotTarget, endpoint: str, params: dict[str, Any] | None = None) -> Any:
    return request_json(
        f"{bot.base_url}/{endpoint}",
        auth=(bot.username, bot.password),
        params=params,
        timeout=4.0,
    )


def cached(key: str, ttl: float, producer):
    now = time.time()
    cached_value = _cache.get(key)
    if cached_value and now - cached_value[0] < ttl:
        return cached_value[1]
    value = producer()
    _cache[key] = (now, value)
    return value


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(JOURNAL_DB) as conn:
        conn.execute(
            """
            create table if not exists trades (
                id integer primary key autoincrement,
                bot_id text not null,
                strategy text not null,
                ft_trade_id text not null,
                pair text,
                side text,
                entry_tag text,
                open_date text,
                open_rate real,
                stake_amount real,
                amount real,
                leverage real,
                status text not null,
                strategy_snapshot_json text not null,
                first_seen_at text not null,
                last_seen_at text not null,
                close_date text,
                close_rate real,
                profit_abs real,
                profit_ratio real,
                exit_reason text,
                hold_minutes integer,
                raw_open_json text,
                raw_close_json text,
                unique(bot_id, ft_trade_id)
            )
            """
        )
        conn.execute(
            """
            create table if not exists events (
                id integer primary key autoincrement,
                event_time text not null,
                bot_id text not null,
                strategy text not null,
                ft_trade_id text not null,
                event_type text not null,
                payload_json text not null
            )
            """
        )
        conn.commit()


def import_strategy_snapshot(strategy_name: str) -> dict[str, Any]:
    cache_key = f"strategy_snapshot:{strategy_name}"

    def load_snapshot():
        if str(STRATEGY_DIR) not in sys.path:
            sys.path.insert(0, str(STRATEGY_DIR))
        for file_path in STRATEGY_DIR.glob("*.py"):
            source = file_path.read_text(encoding="utf-8")
            if f"class {strategy_name}(" not in source:
                continue
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            klass = getattr(module, strategy_name)
            if hasattr(klass, "parameter_snapshot"):
                return klass.parameter_snapshot()
            return {
                "strategy": strategy_name,
                "timeframe": getattr(klass, "timeframe", None),
                "stoploss": getattr(klass, "stoploss", None),
                "minimal_roi": getattr(klass, "minimal_roi", None),
            }
        return {"strategy": strategy_name}

    return cached(cache_key, 15.0, load_snapshot)


def normalize_trade(bot: BotTarget, raw: dict[str, Any]) -> dict[str, Any]:
    trade_id = pick(raw, ["trade_id", "id"], "")
    is_short = bool(pick(raw, ["is_short", "short"], False))
    close_date = pick(raw, ["close_date", "close_date_utc"], None)
    is_open = bool(pick(raw, ["is_open", "open"], close_date is None))
    open_date = pick(raw, ["open_date", "open_date_utc"], None)
    profit_ratio = safe_float(pick(raw, ["profit_ratio", "close_profit"], 0.0))
    profit_abs = safe_float(pick(raw, ["profit_abs", "close_profit_abs", "realized_profit"], 0.0))
    return {
        "bot_id": bot.bot_id,
        "bot_label": bot.label,
        "strategy": bot.strategy,
        "trade_id": str(trade_id),
        "pair": pick(raw, ["pair"], ""),
        "side": "short" if is_short else "long",
        "entry_tag": pick(raw, ["entry_tag", "buy_tag"], ""),
        "open_date": open_date,
        "open_rate": safe_float(pick(raw, ["open_rate", "open_price"], 0.0)),
        "current_rate": safe_float(pick(raw, ["current_rate", "current_price"], 0.0)),
        "close_date": close_date,
        "close_rate": safe_float(pick(raw, ["close_rate", "close_price"], 0.0)),
        "stake_amount": safe_float(pick(raw, ["stake_amount", "stake_amount_fiat"], 0.0)),
        "amount": safe_float(pick(raw, ["amount"], 0.0)),
        "leverage": safe_float(pick(raw, ["leverage"], 1.0), 1.0),
        "profit_abs": profit_abs,
        "profit_ratio": profit_ratio,
        "profit_pct": profit_ratio * 100.0,
        "exit_reason": pick(raw, ["exit_reason", "sell_reason"], ""),
        "is_open": is_open,
        "status": "open" if is_open else "closed",
        "hold_minutes": human_minutes(open_date, close_date),
        "raw": raw,
    }


def load_recent_journal(limit: int = 80) -> list[dict[str, Any]]:
    init_db()
    with sqlite3.connect(JOURNAL_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select *
            from trades
            order by coalesce(close_date, open_date, last_seen_at) desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["strategy_snapshot"] = json.loads(item.pop("strategy_snapshot_json") or "{}")
        item.pop("raw_open_json", None)
        item.pop("raw_close_json", None)
        result.append(item)
    return result


def upsert_journal_trade(bot: BotTarget, trade: dict[str, Any]) -> None:
    if not trade["trade_id"]:
        return
    snapshot = import_strategy_snapshot(bot.strategy)
    now = utc_now_iso()
    raw_json = json.dumps(trade["raw"], ensure_ascii=False, default=str)
    snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
    with sqlite3.connect(JOURNAL_DB) as conn:
        existing = conn.execute(
            "select id, status from trades where bot_id = ? and ft_trade_id = ?",
            (bot.bot_id, trade["trade_id"]),
        ).fetchone()
        if not existing:
            conn.execute(
                """
                insert into trades (
                    bot_id, strategy, ft_trade_id, pair, side, entry_tag, open_date,
                    open_rate, stake_amount, amount, leverage, status,
                    strategy_snapshot_json, first_seen_at, last_seen_at, close_date,
                    close_rate, profit_abs, profit_ratio, exit_reason, hold_minutes,
                    raw_open_json, raw_close_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bot.bot_id,
                    bot.strategy,
                    trade["trade_id"],
                    trade["pair"],
                    trade["side"],
                    trade["entry_tag"],
                    trade["open_date"],
                    trade["open_rate"],
                    trade["stake_amount"],
                    trade["amount"],
                    trade["leverage"],
                    trade["status"],
                    snapshot_json,
                    now,
                    now,
                    trade["close_date"],
                    trade["close_rate"],
                    trade["profit_abs"],
                    trade["profit_ratio"],
                    trade["exit_reason"],
                    trade["hold_minutes"],
                    raw_json,
                    raw_json if trade["status"] == "closed" else None,
                ),
            )
            conn.execute(
                "insert into events (event_time, bot_id, strategy, ft_trade_id, event_type, payload_json) values (?, ?, ?, ?, ?, ?)",
                (now, bot.bot_id, bot.strategy, trade["trade_id"], "opened", raw_json),
            )
        else:
            previous_status = existing[1]
            conn.execute(
                """
                update trades set
                    status = ?,
                    last_seen_at = ?,
                    close_date = coalesce(?, close_date),
                    close_rate = case when ? > 0 then ? else close_rate end,
                    profit_abs = ?,
                    profit_ratio = ?,
                    exit_reason = coalesce(nullif(?, ''), exit_reason),
                    hold_minutes = ?,
                    raw_close_json = case when ? = 'closed' then ? else raw_close_json end
                where bot_id = ? and ft_trade_id = ?
                """,
                (
                    trade["status"],
                    now,
                    trade["close_date"],
                    trade["close_rate"],
                    trade["close_rate"],
                    trade["profit_abs"],
                    trade["profit_ratio"],
                    trade["exit_reason"],
                    trade["hold_minutes"],
                    trade["status"],
                    raw_json,
                    bot.bot_id,
                    trade["trade_id"],
                ),
            )
            if previous_status != "closed" and trade["status"] == "closed":
                conn.execute(
                    "insert into events (event_time, bot_id, strategy, ft_trade_id, event_type, payload_json) values (?, ?, ?, ?, ?, ?)",
                    (now, bot.bot_id, bot.strategy, trade["trade_id"], "closed", raw_json),
                )
        conn.commit()


def fetch_bot(bot: BotTarget) -> dict[str, Any]:
    status = "offline"
    error = None
    show_config: dict[str, Any] = {}
    profit: dict[str, Any] = {}
    balance: dict[str, Any] = {}
    trades_payload: Any = {}
    open_payload: Any = []
    try:
        show_config = bot_get(bot, "show_config")
        profit = bot_get(bot, "profit")
        balance = bot_get(bot, "balance")
        open_payload = bot_get(bot, "status")
        trades_payload = bot_get(bot, "trades", params={"limit": 500, "order_by_id": False})
        status = "online"
    except Exception as exc:
        error = str(exc)

    raw_trades = []
    if isinstance(trades_payload, dict):
        raw_trades = trades_payload.get("trades") or trades_payload.get("data") or []
    elif isinstance(trades_payload, list):
        raw_trades = trades_payload
    raw_open = open_payload if isinstance(open_payload, list) else []

    trades = [normalize_trade(bot, trade) for trade in raw_trades if isinstance(trade, dict)]
    open_trades = [normalize_trade(bot, trade) for trade in raw_open if isinstance(trade, dict)]
    if not open_trades:
        open_trades = [trade for trade in trades if trade["is_open"]]

    for trade in trades[-100:] + open_trades:
        upsert_journal_trade(bot, trade)

    trade_count = safe_int(pick(profit, ["trade_count", "closed_trade_count"], len(trades)))
    winning = safe_int(pick(profit, ["winning_trades", "wins"], 0))
    losing = safe_int(pick(profit, ["losing_trades", "losses"], 0))
    win_rate = (winning / trade_count * 100.0) if trade_count else 0.0
    profit_abs = safe_float(pick(profit, ["profit_all_coin", "profit_closed_coin", "profit_all"], 0.0))
    profit_pct = safe_float(pick(profit, ["profit_all_percent", "profit_closed_percent"], 0.0))
    balance_total = safe_float(
        pick(balance, ["total", "total_bot", "starting_capital"], 0.0),
        default=0.0,
    )
    if balance_total <= 0:
        balance_total = 100.0 + profit_abs

    bot_state = str(pick(show_config, ["state"], "unknown"))
    if status == "online" and bot_state.lower() != "running":
        status = "paused"

    return {
        "id": bot.bot_id,
        "label": bot.label,
        "strategy": bot.strategy,
        "port": bot.port,
        "status": status,
        "state": bot_state,
        "error": error,
        "dry_run": bool(pick(show_config, ["dry_run"], True)),
        "trading_mode": pick(show_config, ["trading_mode"], "futures"),
        "margin_mode": pick(show_config, ["margin_mode"], "isolated"),
        "timeframe": pick(show_config, ["timeframe"], "5m"),
        "balance": balance_total,
        "profit_abs": profit_abs,
        "profit_pct": profit_pct,
        "open_trades": open_trades,
        "open_count": len(open_trades),
        "trade_count": trade_count,
        "win_rate": win_rate,
        "max_drawdown": safe_float(pick(profit, ["max_drawdown", "max_drawdown_abs"], 0.0)),
        "snapshot": import_strategy_snapshot(bot.strategy),
    }


def symbol_from_pair(pair: str) -> str:
    return MARKET_SYMBOLS.get(pair, "BTCUSDT")


def fetch_orderbook(symbol: str) -> dict[str, Any]:
    def produce():
        payload = request_json(
            "https://fapi.binance.com/fapi/v1/depth",
            params={"symbol": symbol, "limit": 10},
            timeout=5.0,
        )
        bids = [[safe_float(price), safe_float(size)] for price, size in payload.get("bids", [])[:10]]
        asks = [[safe_float(price), safe_float(size)] for price, size in payload.get("asks", [])[:10]]
        max_size = max([size for _, size in bids + asks] or [1.0])
        return {
            "symbol": symbol,
            "bids": [{"price": price, "size": size, "depth": size / max_size} for price, size in bids],
            "asks": [{"price": price, "size": size, "depth": size / max_size} for price, size in asks],
        }

    try:
        return cached(f"orderbook:{symbol}", 8.0, produce)
    except Exception as exc:
        return {"symbol": symbol, "bids": [], "asks": [], "error": str(exc)}


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period + 1:
        return None
    gains = []
    losses = []
    for left, right in zip(closes[:-1], closes[1:]):
        delta = right - left
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def fetch_rsi(symbols: list[str]) -> dict[str, Any]:
    def produce():
        values: dict[str, Any] = {}
        for symbol in symbols:
            payload = request_json(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": symbol, "interval": "1h", "limit": 100},
                timeout=6.0,
            )
            closes = [safe_float(row[4]) for row in payload]
            rsi = compute_rsi(closes)
            values[symbol] = None if rsi is None else round(rsi, 1)
        return values

    try:
        return cached("rsi:1h", 90.0, produce)
    except Exception as exc:
        return {"error": str(exc)}


def fetch_funding(symbols: list[str]) -> dict[str, Any]:
    def produce():
        values: dict[str, Any] = {}
        for symbol in symbols:
            payload = request_json(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": symbol},
                timeout=5.0,
            )
            values[symbol] = {
                "rate": safe_float(payload.get("lastFundingRate")) * 100.0,
                "mark_price": safe_float(payload.get("markPrice")),
                "next_time": payload.get("nextFundingTime"),
            }
        return values

    try:
        return cached("funding", 45.0, produce)
    except Exception as exc:
        return {"error": str(exc)}


def fetch_fear_greed() -> dict[str, Any]:
    def produce():
        payload = request_json("https://api.alternative.me/fng/", params={"limit": 2}, timeout=6.0)
        data = payload.get("data", [])
        current = data[0] if data else {}
        previous = data[1] if len(data) > 1 else {}
        return {
            "value": safe_int(current.get("value"), 0),
            "label": current.get("value_classification") or "Unknown",
            "yesterday": safe_int(previous.get("value"), 0) if previous else None,
        }

    try:
        return cached("fear_greed", 600.0, produce)
    except Exception as exc:
        return {"value": None, "label": "Unavailable", "yesterday": None, "error": str(exc)}


def fetch_market(pair: str) -> dict[str, Any]:
    symbol = symbol_from_pair(pair)
    symbols = [symbol_from_pair(pair_name) for pair_name in PAIRS]
    return {
        "pair": pair,
        "symbol": symbol,
        "orderbook": fetch_orderbook(symbol),
        "rsi": fetch_rsi(symbols),
        "funding": fetch_funding(symbols),
        "fear_greed": fetch_fear_greed(),
    }


def build_payload(pair: str | None = None) -> dict[str, Any]:
    init_db()
    selected_pair = pair if pair in PAIRS else PAIRS[0]
    bots = [fetch_bot(bot) for bot in read_bot_targets()]
    open_trades = []
    for bot in bots:
        for trade in bot["open_trades"]:
            open_trades.append(trade)
    total_balance = sum(safe_float(bot["balance"]) for bot in bots)
    total_profit = sum(safe_float(bot["profit_abs"]) for bot in bots)
    starting_balance = 100.0 * len(bots)
    total_profit_pct = (total_profit / starting_balance * 100.0) if starting_balance else 0.0
    dry_run_all = all(bool(bot["dry_run"]) for bot in bots)
    return {
        "generated_at": utc_now_iso(),
        "access_enabled": bool(ACCESS_TOKEN),
        "pairs": PAIRS,
        "summary": {
            "bots_total": len(bots),
            "bots_online": len([bot for bot in bots if bot["status"] == "online"]),
            "bots_running": len([bot for bot in bots if bot["state"] == "running"]),
            "dry_run_all": dry_run_all,
            "total_balance": total_balance,
            "total_profit_abs": total_profit,
            "total_profit_pct": total_profit_pct,
            "open_trades": len(open_trades),
            "starting_balance": starting_balance,
        },
        "bots": bots,
        "open_trades": sorted(open_trades, key=lambda item: item.get("profit_pct", 0), reverse=True),
        "journal": load_recent_journal(80),
        "market": fetch_market(selected_pair),
    }


@app.get("/")
def root(request: Request):
    require_access(request)
    return FileResponse(STATIC_DIR / "miniapp.html")


@app.get("/miniapp")
def miniapp(request: Request):
    require_access(request)
    return FileResponse(STATIC_DIR / "miniapp.html")


@app.get("/api/miniapp")
def api_miniapp(request: Request, pair: str | None = Query(default=None)):
    require_access(request)
    return JSONResponse(build_payload(pair))


@app.get("/api/journal")
def api_journal(request: Request, limit: int = Query(default=80, ge=1, le=500)):
    require_access(request)
    return {"generated_at": utc_now_iso(), "trades": load_recent_journal(limit)}


@app.get("/api/health")
def api_health(request: Request):
    require_access(request)
    checks = []
    for bot in read_bot_targets():
        try:
            payload = bot_get(bot, "show_config")
            checks.append(
                {
                    "bot_id": bot.bot_id,
                    "strategy": bot.strategy,
                    "port": bot.port,
                    "ok": True,
                    "state": payload.get("state"),
                    "dry_run": payload.get("dry_run"),
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "bot_id": bot.bot_id,
                    "strategy": bot.strategy,
                    "port": bot.port,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return {
        "generated_at": utc_now_iso(),
        "dashboard": "ok",
        "journal_db": str(JOURNAL_DB),
        "bots": checks,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dashboard.server:app", host="127.0.0.1", port=8092, reload=False)

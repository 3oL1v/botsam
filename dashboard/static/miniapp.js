const state = {
  access: new URLSearchParams(window.location.search).get("access") || localStorage.getItem("miniapp_access") || "",
  pair: "BTC/USDT:USDT",
  screen: "overview",
  payload: null,
};

if (state.access) {
  localStorage.setItem("miniapp_access", state.access);
}

if (window.Telegram?.WebApp) {
  window.Telegram.WebApp.ready();
  window.Telegram.WebApp.expand();
  window.Telegram.WebApp.setHeaderColor("#071018");
  window.Telegram.WebApp.setBackgroundColor("#071018");
}

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const money = (value) => `${fmt.format(Number(value || 0))} USDT`;
const pct = (value) => `${Number(value || 0) >= 0 ? "+" : ""}${Number(value || 0).toFixed(2)}%`;
const cls = (value) => (Number(value || 0) >= 0 ? "positive" : "negative");
const coin = (pair) => (pair || "?").split("/")[0]?.slice(0, 3) || "?";
const displayPair = (pair) => String(pair || "--").replace(":USDT", "");
const shortStrategy = (name) =>
  String(name || "")
    .replace("VolatilitySqueezeBreakoutAggressive", "Volatility")
    .replace("DonchianVolumeBurst5m", "Donchian")
    .replace("VWAPPullbackMomentumScalp", "VWAP");

function apiUrl(path) {
  const url = new URL(path, window.location.origin);
  if (state.access) url.searchParams.set("access", state.access);
  return url.toString();
}

async function fetchJson(path) {
  const response = await fetch(apiUrl(path), {
    headers: state.access ? { "x-miniapp-token": state.access } : {},
  });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function setRunState(summary) {
  const node = document.getElementById("runState");
  const dot = node.querySelector(".state-dot");
  const allGood = summary?.dry_run_all && summary?.bots_online === summary?.bots_total;
  dot.classList.toggle("warn", !allGood);
  node.querySelector("span:last-child").textContent = allGood ? "Bot Running" : "Degraded";
}

function renderSummary(payload) {
  const { summary } = payload;
  setRunState(summary);
  document.getElementById("totalBalance").innerHTML = `${fmt.format(summary.total_balance)} <small>USDT</small>`;
  setText("totalPnl", `${money(summary.total_profit_abs)} (${pct(summary.total_profit_pct)})`);
  document.getElementById("totalPnl").className = `pnl ${cls(summary.total_profit_abs)}`;
  setText("openCount", String(summary.open_trades));
  setText("botsOnline", `${summary.bots_online}/${summary.bots_total}`);
  setText("dryState", summary.dry_run_all ? "Dry" : "CHECK");
  setText("updatedAt", new Date(payload.generated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }));

  const points = payload.bots.map((bot, index) => 28 - Number(bot.profit_pct || 0) * 2 + index * 7);
  const path = points.length
    ? points.map((y, i) => `${i === 0 ? "M" : "L"} ${2 + i * 56} ${Math.max(4, Math.min(50, y))}`).join(" ")
    : "M2 34 L58 18 L118 8";
  document.getElementById("sparkPath").setAttribute("d", path);
}

function renderStrategies(bots) {
  const root = document.getElementById("strategyStrip");
  root.innerHTML = bots
    .map(
      (bot, index) => `
        <article class="strategy-card ${index === 0 ? "active" : ""}">
          <header>
            <span>${bot.status}</span>
            <i class="status-dot ${bot.status === "online" ? "" : "offline"}"></i>
          </header>
          <h3>${bot.label}</h3>
          <strong class="${cls(bot.profit_abs)}">${money(bot.profit_abs)}</strong>
          <small>${bot.open_count} open · ${Number(bot.win_rate || 0).toFixed(1)}% win</small>
        </article>`
    )
    .join("");
}

function renderOpenTrades(trades) {
  const root = document.getElementById("openTrades");
  if (!trades.length) {
    root.innerHTML = `<div class="empty">Открытых dry-run сделок сейчас нет</div>`;
    return;
  }
  root.innerHTML = trades
    .map(
      (trade) => `
        <article class="trade-card">
          <div class="trade-top">
            <div class="coin">${coin(trade.pair)}</div>
            <div class="trade-title">
              <strong>${displayPair(trade.pair)}</strong>
              <span>${shortStrategy(trade.strategy)} · ${trade.leverage || 1}x · ${trade.entry_tag || "signal"}</span>
            </div>
            <div>
              <div class="side-pill ${trade.side === "short" ? "negative" : "positive"}">${trade.side.toUpperCase()}</div>
              <strong class="${cls(trade.profit_pct)}">${pct(trade.profit_pct)}</strong>
            </div>
          </div>
          <div class="trade-grid">
            <div><span>Entry</span><strong>${fmt.format(trade.open_rate)}</strong></div>
            <div><span>Current</span><strong>${fmt.format(trade.current_rate || trade.open_rate)}</strong></div>
            <div><span>P/L</span><strong class="${cls(trade.profit_abs)}">${money(trade.profit_abs)}</strong></div>
            <div><span>Margin</span><strong>${money(trade.stake_amount)}</strong></div>
            <div><span>Held</span><strong>${trade.hold_minutes ?? 0}m</strong></div>
            <div><span>Bot</span><strong>${trade.bot_label}</strong></div>
          </div>
        </article>`
    )
    .join("");
}

function renderPairTabs(pairs) {
  const root = document.getElementById("pairTabs");
  root.innerHTML = pairs
    .map((pair) => `<button class="pair-tab ${pair === state.pair ? "active" : ""}" data-pair="${pair}" type="button">${coin(pair)}</button>`)
    .join("");
  root.querySelectorAll(".pair-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.pair = button.dataset.pair;
      refresh();
    });
  });
}

function renderOrderbook(orderbook) {
  setText("bookSymbol", orderbook.symbol || "--");
  const rows = [
    ...(orderbook.asks || []).slice(0, 5).reverse().map((row) => ({ ...row, side: "ask" })),
    ...(orderbook.bids || []).slice(0, 5).map((row) => ({ ...row, side: "bid" })),
  ];
  document.getElementById("orderbook").innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <div class="book-row ${row.side}" style="--depth:${Math.max(8, row.depth * 100).toFixed(1)}%">
              <span>${fmt.format(row.price)}</span>
              <strong>${Number(row.size).toFixed(3)}</strong>
            </div>`
        )
        .join("")
    : `<div class="empty">Стакан недоступен</div>`;
}

function renderIndicators(market) {
  const fear = market.fear_greed || {};
  setText("fearValue", fear.value ?? "--");
  setText("fearLabel", fear.label || "--");
  setText("fearYesterday", `Yesterday: ${fear.yesterday ?? "--"}`);

  const funding = market.funding || {};
  document.getElementById("fundingList").innerHTML = Object.entries(funding)
    .filter(([, value]) => typeof value === "object")
    .map(([symbol, value]) => {
      const rate = Number(value.rate || 0);
      return `<div class="compact-row"><span>${symbol.replace("USDT", "")}</span><strong class="${cls(rate)}">${rate >= 0 ? "+" : ""}${rate.toFixed(4)}%</strong></div>`;
    })
    .join("") || `<div class="empty">Funding недоступен</div>`;

  const rsi = market.rsi || {};
  document.getElementById("rsiList").innerHTML = Object.entries(rsi)
    .filter(([, value]) => typeof value === "number")
    .map(([symbol, value]) => {
      const color = value >= 70 ? "negative" : value <= 35 ? "positive" : "";
      return `<div class="compact-row"><span>${symbol.replace("USDT", "")}</span><strong class="${color}">${value.toFixed(1)}</strong></div>`;
    })
    .join("") || `<div class="empty">RSI недоступен</div>`;
}

function renderBotDetails(bots) {
  document.getElementById("botDetails").innerHTML = bots
    .map(
      (bot) => `
        <article class="bot-row">
          <header>
            <h3>${bot.label}</h3>
            <span class="${bot.status === "online" ? "positive" : "negative"}">${bot.status}</span>
          </header>
          <div class="bot-metrics">
            <div><span>P/L</span><strong class="${cls(bot.profit_abs)}">${money(bot.profit_abs)}</strong></div>
            <div><span>Open</span><strong>${bot.open_count}</strong></div>
            <div><span>Win rate</span><strong>${Number(bot.win_rate || 0).toFixed(1)}%</strong></div>
            <div><span>Port</span><strong>${bot.port}</strong></div>
            <div><span>Margin</span><strong>${bot.margin_mode}</strong></div>
            <div><span>State</span><strong>${bot.state}</strong></div>
          </div>
        </article>`
    )
    .join("");
}

function renderJournal(journal) {
  setText("journalCount", String(journal.length));
  document.getElementById("journal").innerHTML = journal.length
    ? journal
        .map((row) => {
          const params = row.strategy_snapshot || {};
          return `
            <article class="journal-row">
              <div class="event-icon">${row.status === "closed" ? "✓" : "↗"}</div>
              <div class="journal-main">
                <strong>${displayPair(row.pair)} · ${shortStrategy(row.strategy)}</strong>
                <span>${row.side?.toUpperCase() || "--"} · ${row.entry_tag || "signal"} · SL ${params.stoploss ?? "--"} · ROI ${JSON.stringify(params.minimal_roi || {})}</span>
              </div>
              <div class="journal-meta">
                <div class="${cls(row.profit_abs)}">${money(row.profit_abs)}</div>
                <div>${row.status}</div>
              </div>
            </article>`;
        })
        .join("")
    : `<div class="empty">Журнал пуст. Записи появятся при первых dry-run сделках.</div>`;
}

function renderHealth(payload) {
  const rows = payload.bots.map((bot) => ({
    title: `${shortStrategy(bot.strategy)} · ${bot.port}`,
    ok: bot.status === "online",
    detail: `${bot.state || "unknown"} · dry-run ${bot.dry_run ? "true" : "check"}`,
  }));
  rows.push({
    title: "Mini App API",
    ok: true,
    detail: payload.access_enabled ? "token protected" : "local open",
  });
  document.getElementById("healthList").innerHTML = rows
    .map(
      (row) => `
        <article class="health-row">
          <header>
            <h3>${row.title}</h3>
            <span class="${row.ok ? "positive" : "negative"}">${row.ok ? "OK" : "DOWN"}</span>
          </header>
          <span class="muted">${row.detail}</span>
        </article>`
    )
    .join("");
}

function render(payload) {
  state.payload = payload;
  renderSummary(payload);
  renderStrategies(payload.bots);
  renderOpenTrades(payload.open_trades);
  renderPairTabs(payload.pairs);
  renderOrderbook(payload.market.orderbook || {});
  renderIndicators(payload.market || {});
  renderBotDetails(payload.bots);
  renderJournal(payload.journal);
  renderHealth(payload);
}

function setScreen(name) {
  state.screen = name;
  document.querySelectorAll("[data-screen]").forEach((node) => node.classList.toggle("hidden", node.dataset.screen !== name));
  if (name === "overview") {
    document.querySelectorAll('[data-screen="overview"]').forEach((node) => node.classList.remove("hidden"));
  }
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.target === name));
}

async function refresh() {
  try {
    const payload = await fetchJson(`/api/miniapp?pair=${encodeURIComponent(state.pair)}`);
    render(payload);
  } catch (error) {
    document.getElementById("runState").innerHTML = `<span class="state-dot warn"></span><span>Ошибка</span>`;
    document.getElementById("openTrades").innerHTML = `<div class="empty">API недоступен: ${error.message}</div>`;
  }
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => setScreen(button.dataset.target));
});

setScreen("overview");
refresh();
setInterval(refresh, 5000);

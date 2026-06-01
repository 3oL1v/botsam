const state = {
  pairs: [],
  selectedPair: localStorage.getItem("selectedPair") || "",
  context: { exchange: "-", trading_mode: "-", timeframe: "1h" },
  timer: null,
};

const el = (id) => document.getElementById(id);

const formatNumber = (value, digits = 4) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (Math.abs(number) >= 1000) return number.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (Math.abs(number) >= 1) return number.toLocaleString("en-US", { maximumFractionDigits: digits });
  return number.toLocaleString("en-US", { maximumFractionDigits: 8 });
};

const formatPercent = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(digits)}%`;
};

const compact = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(Number(value));
};

const setApiStatus = (ok) => {
  el("apiDot").classList.toggle("on", ok);
  el("botState").textContent = ok ? "Running" : "Offline";
};

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function renderPairs() {
  const list = el("pairList");
  list.innerHTML = "";
  state.pairs.forEach((pair) => {
    const button = document.createElement("button");
    button.className = `pair-button ${pair === state.selectedPair ? "active" : ""}`;
    button.type = "button";
    button.innerHTML = `<strong>${pair}</strong><span>${state.context.timeframe} / ${state.context.trading_mode}</span>`;
    button.addEventListener("click", () => {
      state.selectedPair = pair;
      localStorage.setItem("selectedPair", pair);
      renderPairs();
      refreshMarket();
    });
    list.appendChild(button);
  });
}

function fitCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { context, width: rect.width, height: rect.height };
}

function drawLineChart(canvas, rows, key, color, options = {}) {
  const { context, width, height } = fitCanvas(canvas);
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#141512";
  context.fillRect(0, 0, width, height);

  if (!rows || rows.length < 2) return;
  const values = rows.map((row) => row[key]).filter((value) => value !== null && value !== undefined);
  if (values.length < 2) return;

  const min = options.min ?? Math.min(...values);
  const max = options.max ?? Math.max(...values);
  const pad = 16;
  const range = max - min || 1;

  context.strokeStyle = "#292b25";
  context.lineWidth = 1;
  for (let i = 1; i < 5; i += 1) {
    const y = pad + ((height - pad * 2) * i) / 5;
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  if (options.bands) {
    context.strokeStyle = "rgba(214,168,77,.35)";
    context.setLineDash([4, 4]);
    options.bands.forEach((band) => {
      const y = height - pad - ((band - min) / range) * (height - pad * 2);
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    });
    context.setLineDash([]);
  }

  context.beginPath();
  rows.forEach((row, index) => {
    const value = row[key];
    if (value === null || value === undefined) return;
    const x = pad + (index / (rows.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / range) * (height - pad * 2);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });
  context.strokeStyle = color;
  context.lineWidth = 2;
  context.stroke();

  if (key === "close") {
    const gradient = context.createLinearGradient(0, pad, 0, height - pad);
    gradient.addColorStop(0, "rgba(66,199,129,.18)");
    gradient.addColorStop(1, "rgba(66,199,129,0)");
    context.lineTo(width - pad, height - pad);
    context.lineTo(pad, height - pad);
    context.closePath();
    context.fillStyle = gradient;
    context.fill();
  }
}

function renderOrderbook(sideId, rows, type) {
  const container = el(sideId);
  container.innerHTML = "";
  const maxTotal = Math.max(...rows.map((row) => row.total), 1);
  const displayRows = type === "asks" ? [...rows].reverse() : rows;

  displayRows.forEach((row) => {
    const div = document.createElement("div");
    div.className = "book-row";
    div.style.setProperty("--bar", `${Math.max(4, (row.total / maxTotal) * 100)}%`);
    div.innerHTML = `
      <span class="price-cell">${formatNumber(row.price)}</span>
      <span>${formatNumber(row.amount, 3)}</span>
      <span>${formatNumber(row.total, 3)}</span>
    `;
    container.appendChild(div);
  });
}

function renderMarket(data) {
  if (data.available === false) {
    el("errorLine").textContent = data.error || "market unavailable";
    return;
  }

  setApiStatus(true);
  el("errorLine").textContent = "";
  el("pairTitle").textContent = data.pair;
  el("lastPrice").textContent = formatNumber(data.ticker.last);

  const change = Number(data.ticker.percentage || 0);
  el("change24h").textContent = `${formatPercent(change)} 24h`;
  el("change24h").className = `change ${change >= 0 ? "up" : "down"}`;

  el("bidAsk").textContent = `${formatNumber(data.ticker.bid)} / ${formatNumber(data.ticker.ask)}`;
  el("spread").textContent = formatNumber(data.orderbook.spread, 6);
  el("rsiValue").textContent = data.rsi === null ? "-" : Number(data.rsi).toFixed(1);
  el("rsiValue").className = data.rsi >= 70 ? "down" : data.rsi <= 35 ? "up" : "";
  el("volume24h").textContent = compact(data.ticker.quoteVolume);

  renderOrderbook("asks", data.orderbook.asks, "asks");
  renderOrderbook("bids", data.orderbook.bids, "bids");
  const mid = data.ticker.bid && data.ticker.ask ? (Number(data.ticker.bid) + Number(data.ticker.ask)) / 2 : data.ticker.last;
  el("midPrice").textContent = formatNumber(mid);

  drawLineChart(el("priceChart"), data.chart, "close", "#42c781");
  drawLineChart(el("rsiChart"), data.chart, "rsi", "#d6a84d", { min: 0, max: 100, bands: [35, 70] });

  const fg = data.fear_greed || {};
  el("fearGreed").textContent = fg.available ? `${fg.value} · ${fg.classification}` : "Unavailable";
  el("fearGauge").style.width = fg.available ? `${fg.value}%` : "0%";

  const funding = data.funding || {};
  el("fundingRate").textContent = funding.available ? formatPercent(funding.percent, 4) : "Unavailable";
  el("fundingRate").className = funding.percent >= 0 ? "up" : "down";
  el("fundingNote").textContent = funding.symbol || "public perpetual data";

  const bot = data.bot || {};
  el("openTrades").textContent = bot.available
    ? `${bot.open_trades || 0} / ${bot.max_open_trades || 0}`
    : "Freqtrade offline";
  el("profitLine").textContent = bot.available
    ? `profit ${formatPercent(bot.profit_all_percent || 0)} · trades ${bot.trade_count || 0}`
    : bot.error || "";

  el("updatedAt").textContent = new Date(data.updated_at).toLocaleTimeString();
}

async function refreshMarket() {
  if (!state.selectedPair) return;
  try {
    const data = await getJson(`/api/market?pair=${encodeURIComponent(state.selectedPair)}`);
    renderMarket(data);
  } catch (error) {
    setApiStatus(false);
    el("errorLine").textContent = error.message;
  }
}

async function boot() {
  try {
    const data = await getJson("/api/pairs");
    state.pairs = data.pairs || [];
    state.context = data.context || state.context;
    el("appSubtitle").textContent = `${state.context.exchange} ${state.context.trading_mode} monitor for Freqtrade paper trading`;
    if (!state.pairs.includes(state.selectedPair)) state.selectedPair = state.pairs[0] || "";
    renderPairs();
    await refreshMarket();
    state.timer = window.setInterval(refreshMarket, 10_000);
  } catch (error) {
    setApiStatus(false);
    el("errorLine").textContent = error.message;
  }
}

window.addEventListener("resize", () => refreshMarket());
boot();

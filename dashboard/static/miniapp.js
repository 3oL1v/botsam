const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  token: new URLSearchParams(window.location.search).get("access") || localStorage.getItem("miniappAccess") || "",
  data: null,
  timer: null,
};

if (state.token) {
  localStorage.setItem("miniappAccess", state.token);
}

const $ = (id) => document.getElementById(id);

const formatNumber = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  if (Math.abs(number) >= 1000) return number.toLocaleString("en-US", { maximumFractionDigits: digits });
  if (Math.abs(number) >= 1) return number.toLocaleString("en-US", { maximumFractionDigits: digits });
  return number.toLocaleString("en-US", { maximumFractionDigits: 6 });
};

const formatMoney = (value, currency = "USDT") => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${formatNumber(value, 2)} ${currency}`;
};

const formatPercent = (value, digits = 2) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(digits)}%`;
};

const setSigned = (element, value) => {
  element.textContent = formatPercent(value);
  element.classList.toggle("down", Number(value) < 0);
  element.classList.toggle("up", Number(value) >= 0);
};

async function getJson(url) {
  const headers = state.token ? { "X-Miniapp-Token": state.token } : {};
  const response = await fetch(url, { headers, cache: "no-store" });
  if (!response.ok) throw new Error(response.status === 401 ? "Нет доступа" : `${response.status} ${response.statusText}`);
  return response.json();
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

function drawSpark(rows) {
  const canvas = $("priceSpark");
  const { context, width, height } = fitCanvas(canvas);
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#101210";
  context.fillRect(0, 0, width, height);

  if (!rows || rows.length < 2) return;
  const closes = rows.map((row) => Number(row.close)).filter((value) => Number.isFinite(value));
  if (closes.length < 2) return;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const pad = 16;

  context.strokeStyle = "#252b25";
  context.lineWidth = 1;
  for (let i = 1; i <= 3; i += 1) {
    const y = pad + ((height - pad * 2) * i) / 4;
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  context.beginPath();
  closes.forEach((close, index) => {
    const x = pad + (index / (closes.length - 1)) * (width - pad * 2);
    const y = height - pad - ((close - min) / range) * (height - pad * 2);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  });

  const line = context.createLinearGradient(0, 0, width, 0);
  line.addColorStop(0, "#43d17e");
  line.addColorStop(1, "#8ab3ff");
  context.strokeStyle = line;
  context.lineWidth = 2;
  context.stroke();

  context.lineTo(width - pad, height - pad);
  context.lineTo(pad, height - pad);
  context.closePath();
  const fill = context.createLinearGradient(0, pad, 0, height - pad);
  fill.addColorStop(0, "rgba(67,209,126,.2)");
  fill.addColorStop(1, "rgba(67,209,126,0)");
  context.fillStyle = fill;
  context.fill();
}

function tradeCard(trade) {
  const profit = Number(trade.profit_percent || 0);
  const sideClass = trade.is_short ? "short" : "long";
  const rate = trade.is_open ? trade.current_rate : trade.close_rate;
  return `
    <article class="trade-card">
      <div class="trade-main">
        <div class="trade-pair">
          <strong>${trade.pair || "-"}</strong>
          <span class="side ${sideClass}">${trade.side || "-"}</span>
        </div>
        <div class="trade-profit">
          <strong class="${profit < 0 ? "down" : "up"}">${formatPercent(profit)}</strong>
          <span>${formatMoney(trade.profit_abs, "USDT")}</span>
        </div>
      </div>
      <div class="trade-meta">
        <div>
          <span>Вход</span>
          <strong>${formatNumber(trade.open_rate, 6)}</strong>
        </div>
        <div>
          <span>${trade.is_open ? "Сейчас" : "Выход"}</span>
          <strong>${formatNumber(rate, 6)}</strong>
        </div>
        <div>
          <span>Stake</span>
          <strong>${formatMoney(trade.stake_amount, "USDT")}</strong>
        </div>
      </div>
    </article>
  `;
}

function emptyCard(title, text) {
  return `
    <div class="empty-card">
      <div>
        <strong>${title}</strong>
        <span>${text}</span>
      </div>
    </div>
  `;
}

function renderTrades() {
  const open = state.data?.open_trades || [];
  const recent = state.data?.recent_trades || [];

  $("openSubtitle").textContent = `${open.length} active`;
  $("historySubtitle").textContent = `${recent.length} closed`;

  $("openTrades").innerHTML = open.length
    ? open.map(tradeCard).join("")
    : emptyCard("Открытых сделок нет", "Бот ждёт сигнал стратегии.");

  $("recentTrades").innerHTML = recent.length
    ? recent.map(tradeCard).join("")
    : emptyCard("История пустая", "Закрытые dry-run сделки появятся здесь.");
}

function render(data) {
  state.data = data;
  const context = data.context || {};
  const summary = data.summary || {};
  const market = data.market || {};
  const stake = context.stake_currency || "USDT";

  $("statusDot").classList.toggle("on", Boolean(summary.available));
  $("runState").textContent = summary.available ? "Running" : "Offline";
  $("exchangeMode").textContent = `${context.exchange || "-"} ${context.trading_mode || "-"}`;
  $("strategyName").textContent = context.strategy || context.bot_name || "Freqtrade";

  $("profitValue").textContent = formatMoney(summary.profit_all_coin || 0, stake);
  setSigned($("profitPercent"), summary.profit_all_percent || 0);
  $("balanceValue").textContent = formatMoney(summary.balance_total ?? summary.balance_value, stake);
  $("openCount").textContent = `${summary.open_trades || 0} / ${summary.max_open_trades || 0}`;
  $("winRate").textContent = formatPercent(summary.winrate || 0);

  $("marketPair").textContent = market.pair || "-";
  $("marketPrice").textContent = formatNumber(market.last, 3);
  setSigned($("marketChange"), market.change24h || 0);
  $("rsiValue").textContent = market.rsi === null || market.rsi === undefined ? "-" : Number(market.rsi).toFixed(1);
  $("rsiValue").className = Number(market.rsi) >= 70 ? "down" : Number(market.rsi) <= 35 ? "up" : "";

  const fg = market.fear_greed || {};
  $("fearGreed").textContent = fg.available ? `${fg.value} ${fg.classification}` : "-";

  const funding = market.funding || {};
  $("fundingRate").textContent = funding.available ? formatPercent(funding.percent, 4) : "-";
  $("fundingRate").className = Number(funding.percent) < 0 ? "down" : "up";

  drawSpark(market.chart || []);
  renderTrades();

  $("updatedAt").textContent = new Date(data.updated_at || Date.now()).toLocaleTimeString();
  $("errorLine").textContent = (data.errors || []).slice(0, 1).join("");
}

async function refresh() {
  $("refreshBtn").disabled = true;
  try {
    render(await getJson("/api/miniapp"));
  } catch (error) {
    $("statusDot").classList.remove("on");
    $("runState").textContent = "Offline";
    $("errorLine").textContent = error.message;
  } finally {
    $("refreshBtn").disabled = false;
  }
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    $(`view-${button.dataset.tab}`).classList.add("active");
  });
});

$("refreshBtn").addEventListener("click", refresh);
window.addEventListener("resize", () => state.data && drawSpark(state.data.market?.chart || []));

refresh();
state.timer = window.setInterval(refresh, 10000);

/* =====================================================
   PARTHSARTHI CAPITAL · DASHBOARD APP
   Fetches engine_a_current.json and renders the dashboard.
   Falls back to embedded demo data if fetch fails.
   ===================================================== */

const CONFIG = {
  // Live JSON URL on user's GitHub repo (raw content)
  jsonUrl: "https://raw.githubusercontent.com/abhiarjun231-netizen/Engine-A-Dashboard-v2/main/data/core/engine_a_current.json",
  historyUrl: "https://raw.githubusercontent.com/abhiarjun231-netizen/Engine-A-Dashboard-v2/main/data/core/engine_a_history.csv",
  // Refresh quietly every 5 min
  refreshIntervalMs: 5 * 60 * 1000,
};

// ============ DEMO FALLBACK DATA ============
const DEMO_DATA = {
  last_compute: "2026-05-15 19:55:37 IST",
  schema_version: "v2.1",
  score: 45,
  max_available: 100,
  regime: "ACTIVE",
  equity_allocation: 55,
  guidance: "Normal deployment",
  pending_count: 0,
  components: {
    "C1_valuation": { weight: 22, name: "Valuation", sub_inputs: {
      "yield_gap":       { value: -2.12, score: 0, max: 10, status: "OK", note: "Yield gap negative; bonds outyielding equity earnings" },
      "nifty_pe_pctile": { value: 7, score: 6, max: 6, status: "OK", note: "Nifty PE at 7th percentile of 10Y (cheap)" },
      "mcap_gdp_ratio":  { value: 242.75, score: 0, max: 6, status: "OK", note: "MCap/GDP 242.8% (very expensive vs 20Y range)" }
    }},
    "C2_credit_rates": { weight: 14, name: "Credit & Rates", sub_inputs: {
      "aaa_spread_bps":     { value: 35, score: 8, max: 8, status: "OK", note: "AAA-GSec spread 35 bps (very tight, healthy)" },
      "yield_curve_10y_2y": { value: 0.45, score: 2, max: 3, status: "OK", note: "Curve positive but flat" },
      "credit_growth_yoy":  { value: 16, score: 3, max: 3, status: "OK", note: "Bank credit +16% YoY (strong)" }
    }},
    "C3_trend_breadth": { weight: 13, name: "Trend & Breadth", sub_inputs: {
      "nifty_vs_200dma":  { value: -2.4, score: 2, max: 7, status: "OK", note: "Nifty 50 marginally below 200DMA" },
      "pct_above_200dma": { value: 43, score: 3, max: 6, status: "OK", note: "43% of Nifty 500 above 200DMA (mixed breadth)" }
    }},
    "C4_volatility": { weight: 10, name: "Volatility", sub_inputs: {
      "india_vix_pctile": { value: 38, score: 4, max: 6, status: "OK", note: "India VIX at 38th percentile (calm)" },
      "vix_vs_30d_avg":   { value: -5.2, score: 2, max: 4, status: "OK", note: "VIX -5% vs 30D average" }
    }},
    "C5_flows": { weight: 12, name: "Flows", sub_inputs: {
      "fii_latest_month":  { value: -53835, score: 0, max: 5, status: "OK", note: "FII -53,835 Cr (heavy outflow)" },
      "dii_latest_month":  { value: 52566, score: 4, max: 4, status: "OK", note: "DII +52,566 Cr (very strong)" },
      "sip_yoy":           { value: 17, score: 2, max: 3, status: "OK", note: "SIP YoY +17% (healthy)" }
    }},
    "C6_macro_india": { weight: 12, name: "Macro India", sub_inputs: {
      "rbi_stance": { value: "Neutral", score: 2, max: 3, status: "OK", note: "RBI Neutral stance" },
      "cpi_yoy":    { value: 3.8, score: 2, max: 3, status: "OK", note: "CPI 3.8%, insufficient history for direction (defaulting Stable)" },
      "pmi_mfg":    { value: 55.9, score: 3, max: 3, status: "OK", note: "PMI 55.9 (strong expansion)" },
      "gst_yoy":    { value: 8.7, score: 2, max: 3, status: "OK", note: "GST +8.7% YoY" }
    }},
    "C7_global_cross_asset": { weight: 12, name: "Global Cross-Asset", sub_inputs: {
      "us_10y_direction": { value: 4.42, score: 1, max: 2, status: "OK", note: "US 10Y stable" },
      "dxy":              { value: 99.8, score: 2, max: 2, status: "OK", note: "DXY softening (good for EM)" },
      "us_vix":           { value: 17, score: 2, max: 3, status: "OK", note: "US VIX moderate" },
      "inr_direction":    { value: 84.5, score: 1, max: 2, status: "OK", note: "INR mildly weaker" },
      "gold_inr_vs_6m":   { value: 7.2, score: 2, max: 3, status: "OK", note: "Gold (INR) +7% vs 6M" }
    }},
    "C8_crude": { weight: 5, name: "Crude", sub_inputs: {
      "brent_vs_6m": { value: -3.5, score: 3, max: 5, status: "OK", note: "Brent -3.5% vs 6M (favorable for India)" }
    }}
  },
  auto_inputs: {
    nifty_50:   { value: 24365.40, delta_pct: -0.45 },
    india_vix:  { value: 13.85,    delta_pct: 1.20 },
    inr_usd:    { value: 84.52,    delta_pct: -0.08 },
    brent:      { value: 76.30,    delta_pct: 0.25 },
    goldbees:   { value: 67.45,    delta_pct: 0.80 },
    us_10y:     { value: 4.42,     delta_pct: -0.30 }
  }
};

const DEMO_HISTORY = [
  { date: "2026-04-13", score: 38 },
  { date: "2026-04-20", score: 35 },
  { date: "2026-04-27", score: 32 },
  { date: "2026-05-04", score: 28 },
  { date: "2026-05-11", score: 41 },
  { date: "2026-05-15", score: 45 }
];

// ============ HELPERS ============
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function fmtNumber(n, decimals = 1) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  if (Math.abs(n) >= 100000) return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
  if (Math.abs(n) >= 1000)   return n.toLocaleString("en-IN", { maximumFractionDigits: decimals });
  return n.toFixed(decimals);
}

function fmtSigned(n, decimals = 2) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return sign + n.toFixed(decimals) + "%";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function getCurrentDateLine() {
  const opts = { weekday: "long", year: "numeric", month: "long", day: "numeric" };
  return new Date().toLocaleDateString("en-IN", opts);
}

// Track state for transition animations
let PREV_STATE = { score: null, regime: null };

// Animated counter (supports starting from any value, not just 0)
function animateCounter(el, target, duration = 1400, startFrom = null) {
  if (!el) return;
  const start = startFrom !== null ? startFrom : 0;
  const startTime = performance.now();
  const step = (now) => {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(start + (target - start) * eased);
    el.textContent = value;
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = target;
  };
  requestAnimationFrame(step);
}

// ============ DATA FETCH ============
async function fetchData() {
  try {
    const res = await fetch(CONFIG.jsonUrl, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return { data, isDemo: false };
  } catch (err) {
    console.warn("Live fetch failed, using demo data:", err.message);
    return { data: DEMO_DATA, isDemo: true };
  }
}

async function fetchHistory() {
  try {
    const res = await fetch(CONFIG.historyUrl, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    return parseHistoryCsv(text);
  } catch (err) {
    console.warn("History fetch failed, using demo history:", err.message);
    return DEMO_HISTORY;
  }
}

function parseHistoryCsv(text) {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
  const dateIdx  = headers.findIndex(h => h.includes("date") || h.includes("timestamp"));
  const scoreIdx = headers.findIndex(h => h === "score");
  if (dateIdx < 0 || scoreIdx < 0) return [];
  return lines.slice(1).map(line => {
    const cells = line.split(",");
    return {
      date: (cells[dateIdx] || "").trim().slice(0, 10),
      score: parseFloat(cells[scoreIdx])
    };
  }).filter(r => !isNaN(r.score));
}

// ============ RENDER: TICKER ============
function renderTicker(auto) {
  const items = [
    { label: "Nifty 50",    key: "nifty_50",  decimals: 2 },
    { label: "India VIX",   key: "india_vix", decimals: 2 },
    { label: "USD/INR",     key: "inr_usd",   decimals: 2 },
    { label: "Brent",       key: "brent",     decimals: 2, unit: "$" },
    { label: "GoldBees",    key: "goldbees",  decimals: 2 },
    { label: "US 10Y",      key: "us_10y",    decimals: 2, unit: "%" }
  ];

  const blocks = items.map(it => {
    const a = auto[it.key];
    if (!a) return "";
    const val = (it.unit || "") + fmtNumber(a.value, it.decimals);
    const dp = a.delta_pct;
    let deltaClass = "flat";
    let deltaText = "—";
    if (typeof dp === "number") {
      if (dp > 0.05)  deltaClass = "up";
      if (dp < -0.05) deltaClass = "down";
      deltaText = (dp > 0 ? "+" : "") + dp.toFixed(2) + "%";
    }
    return `
      <span class="ticker-item">
        <span class="ticker-label">${escapeHtml(it.label)}</span>
        <span class="ticker-value">${escapeHtml(val)}</span>
        <span class="ticker-delta ${deltaClass}">${escapeHtml(deltaText)}</span>
      </span>
      <span style="color: var(--ink-500); opacity: 0.4;">·</span>
    `;
  }).join("");

  // duplicate to enable infinite scroll
  $("#ticker-track").innerHTML = blocks + blocks;
}

// ============ RENDER: HERO ============
function renderHero(data) {
  const score = data.score ?? 0;
  const max   = data.max_available ?? 100;
  const regime = (data.regime || "loading").toUpperCase();
  const allocation = data.equity_allocation ?? 0;

  // If this is a refresh (not first load), smoothly transition from previous score
  if (PREV_STATE.score !== null && PREV_STATE.score !== score) {
    animateCounter($("#score-value"), score, 800, PREV_STATE.score);
  } else if (PREV_STATE.score === null) {
    // First load: count up from 0
    animateCounter($("#score-value"), score, 1400, 0);
  } else {
    // No change
    $("#score-value").textContent = score;
  }

  $("#score-max").textContent  = "100";
  $("#score-pct").textContent  = `${score} of 100 points · ${max}/100 unlocked`;

  const badge = $("#regime-badge");
  const previousRegime = badge.getAttribute("data-regime");
  badge.setAttribute("data-regime", regime);
  $("#regime-label").textContent = `Regime · ${regime}`;
  $("#allocation-figure").textContent = allocation;

  // Regime change shimmer
  if (PREV_STATE.regime && PREV_STATE.regime !== regime && previousRegime !== "loading") {
    badge.classList.remove("shimmer");
    void badge.offsetWidth; // force reflow
    badge.classList.add("shimmer");
    setTimeout(() => badge.classList.remove("shimmer"), 1800);
  }

  $("#regime-guidance").textContent = data.guidance || "—";
  $("#schema-version").textContent = data.schema_version || "v2.1";

  $("#meta-date").textContent = getCurrentDateLine();
  $("#footer-compute").textContent = data.last_compute || "—";
  $("#footer-schema").textContent  = data.schema_version || "v2.1";

  // Save state for next refresh comparison
  PREV_STATE = { score, regime };
}

// ============ RENDER: PENDING ============
function renderPending(data) {
  const banner = $("#pending-banner");
  const count = data.pending_count ?? 0;
  if (count > 0) {
    $("#pending-count-text").textContent =
      count === 1 ? "1 input pending manual entry" : `${count} inputs pending manual entry`;
    banner.hidden = false;
  } else {
    banner.hidden = true;
  }
}

// ============ RENDER: COMPONENT CARDS ============
function classifyHealth(achieved, max) {
  if (max === 0) return "pending";
  const ratio = achieved / max;
  if (ratio >= 0.7)  return "strong";
  if (ratio >= 0.35) return "ok";
  if (ratio > 0)     return "weak";
  return "pending";
}

function renderComponents(data) {
  const container = $("#components");
  const comps = data.components || {};
  const order = [
    "C1_valuation", "C2_credit_rates", "C3_trend_breadth", "C4_volatility",
    "C5_flows", "C6_macro_india", "C7_global_cross_asset", "C8_crude"
  ];
  const labels = {
    C1_valuation: "C1", C2_credit_rates: "C2", C3_trend_breadth: "C3",
    C4_volatility: "C4", C5_flows: "C5", C6_macro_india: "C6",
    C7_global_cross_asset: "C7", C8_crude: "C8"
  };

  container.innerHTML = "";

  order.forEach(key => {
    const c = comps[key];
    if (!c) return;
    const subs = c.sub_inputs || {};
    const subList = Object.entries(subs);

    let achieved = 0, max = 0;
    subList.forEach(([_, s]) => {
      if (s.status === "OK") achieved += (s.score || 0);
      max += (s.max || 0);
    });

    const health = classifyHealth(achieved, max);

    const card = document.createElement("div");
    card.className = "comp";
    card.setAttribute("data-health", health);

    const subRows = subList.map(([k, s]) => {
      const val = (s.value !== null && s.value !== undefined) ? s.value : "—";
      const isPending = s.status === "PENDING_MANUAL";
      const isError   = s.status === "ERROR";
      const chip = isPending ? `<span class="sub-status-chip">pending</span>` : "";
      const fmtVal = typeof val === "number" ? fmtNumber(val, 2) : escapeHtml(String(val));
      return `
        <div class="sub-input">
          <div class="sub-key">${escapeHtml(k)}</div>
          <div class="sub-figure" data-status="${escapeHtml(s.status || 'OK')}">
            ${chip}${isPending ? "—" : fmtVal}
            <span class="small-frac"> · ${s.score ?? "—"}/${s.max ?? "—"}</span>
          </div>
          ${s.note ? `<div class="sub-note">${escapeHtml(s.note)}</div>` : ""}
        </div>
      `;
    }).join("");

    card.innerHTML = `
      <button class="comp-head" type="button" aria-expanded="false">
        <span class="comp-stripe"></span>
        <span class="comp-info">
          <span class="comp-id">${labels[key]}</span>
          <span class="comp-name">${escapeHtml(c.name || "")}</span>
        </span>
        <span class="comp-figure">${achieved}<span class="out-of">/${max}</span></span>
        <svg class="comp-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      <div class="comp-body">${subRows}</div>
    `;

    // Click toggles
    const head = card.querySelector(".comp-head");
    head.addEventListener("click", () => {
      const isOpen = card.hasAttribute("open");
      if (isOpen) { card.removeAttribute("open"); head.setAttribute("aria-expanded", "false"); }
      else        { card.setAttribute("open", ""); head.setAttribute("aria-expanded", "true"); }
    });

    container.appendChild(card);
  });

  // Scroll-triggered reveal — each card fades in with stagger as user scrolls
  if (typeof IntersectionObserver !== "undefined" &&
      !(typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    const allCards = container.querySelectorAll(".comp");
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const card = entry.target;
          const idx = Array.from(allCards).indexOf(card);
          setTimeout(() => card.classList.add("revealed"), idx * 50);
          observer.unobserve(card);
        }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -10% 0px" });
    allCards.forEach(card => observer.observe(card));
  } else {
    container.querySelectorAll(".comp").forEach(c => c.classList.add("revealed"));
  }
}

// ============ RENDER: RADAR (animated) ============
function renderRadar(data, animate = true) {
  const svg = $("#radar");
  if (!svg) return;
  const comps = data.components || {};
  const order = [
    "C1_valuation", "C2_credit_rates", "C3_trend_breadth", "C4_volatility",
    "C5_flows", "C6_macro_india", "C7_global_cross_asset", "C8_crude"
  ];
  const shortLabels = {
    C1_valuation: "Valuation", C2_credit_rates: "Credit", C3_trend_breadth: "Trend",
    C4_volatility: "Vol", C5_flows: "Flows", C6_macro_india: "Macro",
    C7_global_cross_asset: "Global", C8_crude: "Crude"
  };

  const N = order.length;
  const radius = 110;

  const ratios = order.map(key => {
    const c = comps[key];
    if (!c) return 0;
    const subs = Object.values(c.sub_inputs || {});
    const max = subs.reduce((a, s) => a + (s.max || 0), 0);
    const ach = subs.reduce((a, s) => a + (s.status === "OK" ? (s.score || 0) : 0), 0);
    return max > 0 ? ach / max : 0;
  });

  const points = order.map((_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI / N);
    const r = radius * ratios[i];
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  });
  const axisEnd = order.map((_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI / N);
    return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius };
  });
  const labelPos = order.map((_, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI / N);
    return { x: Math.cos(angle) * (radius + 22), y: Math.sin(angle) * (radius + 22) };
  });

  const rings = [0.25, 0.5, 0.75].map(r =>
    `<circle class="radar-ring" cx="0" cy="0" r="${radius * r}"/>`
  ).join("");
  const axes = axisEnd.map(p =>
    `<line class="radar-axis" x1="0" y1="0" x2="${p.x.toFixed(2)}" y2="${p.y.toFixed(2)}"/>`
  ).join("");

  const polygonPoints = points.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");

  const dots = points.map((p, i) =>
    `<circle class="radar-point" data-idx="${i}" cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="4" style="opacity:0;"/>`
  ).join("");

  const labels = order.map((key, i) => {
    const p = labelPos[i];
    const pct = Math.round(ratios[i] * 100);
    const anchor = Math.abs(p.x) < 5 ? "middle" : (p.x > 0 ? "start" : "end");
    return `
      <text class="radar-label" x="${p.x.toFixed(2)}" y="${p.y.toFixed(2)}" text-anchor="${anchor}" dominant-baseline="middle" style="opacity:0;">${shortLabels[key]}</text>
      <text class="radar-label-pct" x="${p.x.toFixed(2)}" y="${(p.y + 10).toFixed(2)}" text-anchor="${anchor}" dominant-baseline="middle" style="opacity:0;">${pct}%</text>
    `;
  }).join("");

  svg.innerHTML = `
    <circle class="radar-ring-outer" cx="0" cy="0" r="${radius}"/>
    ${rings}
    ${axes}
    <polygon class="radar-value" points="${polygonPoints}" style="opacity:0;"/>
    ${dots}
    ${labels}
  `;

  if (!animate || (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    svg.querySelectorAll("[style*='opacity:0']").forEach(el => el.style.opacity = 1);
    return;
  }

  // Stagger dot appearances along axes (300ms total stagger), then polygon fills, then labels fade in
  const allDots = svg.querySelectorAll(".radar-point");
  allDots.forEach((dot, i) => {
    setTimeout(() => {
      dot.style.transition = "opacity 0.3s ease, transform 0.4s cubic-bezier(0.22, 1, 0.36, 1)";
      dot.style.opacity = 1;
      // brief pop effect
      dot.style.transformOrigin = "center";
      dot.animate(
        [{ transform: "scale(0)" }, { transform: "scale(1.4)", offset: 0.6 }, { transform: "scale(1)" }],
        { duration: 400, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "forwards" }
      );
    }, 80 + i * 60);
  });

  // Polygon fades in after all dots
  setTimeout(() => {
    const poly = svg.querySelector(".radar-value");
    if (poly) {
      poly.style.transition = "opacity 0.5s ease";
      poly.style.opacity = 1;
    }
  }, 80 + N * 60 + 100);

  // Labels fade in last
  setTimeout(() => {
    svg.querySelectorAll(".radar-label, .radar-label-pct").forEach((el, i) => {
      setTimeout(() => {
        el.style.transition = "opacity 0.4s ease";
        el.style.opacity = 1;
      }, i * 20);
    });
  }, 80 + N * 60 + 200);
}

// ============ RENDER: HISTORY (animated) ============
function renderHistory(history, animate = true) {
  const svg = $("#history");
  const empty = $("#history-empty");
  if (!svg) return;

  if (!history || history.length < 2) {
    svg.innerHTML = "";
    empty.style.display = "flex";
    return;
  }
  empty.style.display = "none";

  const data = history.slice(-30);

  const W = 600, H = 240;
  const padX = 30, padY = 20;
  const innerW = W - padX * 2;
  const innerH = H - padY * 2;

  const yScale = (score) => padY + (1 - score / 100) * innerH;
  const xScale = (i) => padX + (i / (data.length - 1)) * innerW;

  const bands = [
    { cls: "hist-band-freeze",     from: 0,   to: 25  },
    { cls: "hist-band-cautious",   from: 25,  to: 35  },
    { cls: "hist-band-active",     from: 35,  to: 65  },
    { cls: "hist-band-aggressive", from: 65,  to: 100 }
  ];

  const bandRects = bands.map(b => {
    const y1 = yScale(b.to), y2 = yScale(b.from);
    return `<rect class="${b.cls}" x="${padX}" y="${y1}" width="${innerW}" height="${y2 - y1}"/>`;
  }).join("");

  const linePath = data.map((d, i) =>
    `${i === 0 ? "M" : "L"}${xScale(i).toFixed(1)},${yScale(d.score).toFixed(1)}`
  ).join(" ");

  const dots = data.map((d, i) =>
    `<circle class="hist-point" data-idx="${i}" cx="${xScale(i).toFixed(1)}" cy="${yScale(d.score).toFixed(1)}" r="3.5" style="opacity:0;"/>`
  ).join("");

  const yLabels = [0, 25, 50, 75, 100].map(v =>
    `<text class="hist-axis-label" x="${padX - 4}" y="${yScale(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle">${v}</text>`
  ).join("");

  const firstDate = data[0].date.slice(5);
  const lastDate  = data[data.length - 1].date.slice(5);
  const xLabels = `
    <text class="hist-axis-label" x="${padX}" y="${H - 4}" text-anchor="start">${firstDate}</text>
    <text class="hist-axis-label" x="${W - padX}" y="${H - 4}" text-anchor="end">${lastDate}</text>
  `;

  svg.innerHTML = bandRects + yLabels + `<path id="hist-line-path" class="hist-line" d="${linePath}"/>` + dots + xLabels;

  if (!animate || (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches)) {
    svg.querySelectorAll(".hist-point").forEach(el => el.style.opacity = 1);
    return;
  }

  // Line draw animation using stroke-dasharray
  const path = svg.querySelector("#hist-line-path");
  if (path) {
    const len = path.getTotalLength();
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len;
    // Force reflow
    void path.getBoundingClientRect();
    path.style.transition = "stroke-dashoffset 1.4s cubic-bezier(0.5, 0, 0.2, 1)";
    path.style.strokeDashoffset = 0;
  }

  // Dots pop in progressively as line passes them
  const allDots = svg.querySelectorAll(".hist-point");
  const totalDuration = 1400;
  const perDotDelay = totalDuration / data.length;
  allDots.forEach((dot, i) => {
    setTimeout(() => {
      dot.style.transition = "opacity 0.3s ease";
      dot.style.opacity = 1;
      dot.animate(
        [{ transform: "scale(0)" }, { transform: "scale(1.5)", offset: 0.6 }, { transform: "scale(1)" }],
        { duration: 350, easing: "cubic-bezier(0.22, 1, 0.36, 1)", fill: "forwards" }
      );
    }, 200 + i * perDotDelay);
  });
}

// ============ DEMO BANNER ============
function showDemoBanner() {
  if (document.querySelector(".demo-banner")) return;
  const banner = document.createElement("div");
  banner.className = "demo-banner";
  banner.textContent = "Demo mode · Live data not yet available";
  document.body.prepend(banner);
  document.body.classList.add("demo-mode");
}

// ============ MAIN ============
async function init() {
  // Fire fetches in parallel
  const [{ data, isDemo }, history] = await Promise.all([
    fetchData(),
    fetchHistory()
  ]);

  if (isDemo) showDemoBanner();

  // Render
  renderHero(data);
  renderTicker(data.auto_inputs || {});
  renderPending(data);
  renderComponents(data);
  renderRadar(data);
  renderHistory(history);
}

init();

// Quiet auto-refresh
setInterval(async () => {
  try {
    const { data } = await fetchData();
    const history = await fetchHistory();
    renderHero(data);  // score/regime animate only if changed
    renderTicker(data.auto_inputs || {});
    renderPending(data);
    renderComponents(data);
    renderRadar(data, false);   // don't re-animate radar on refresh
    renderHistory(history, false);  // don't re-animate history on refresh
  } catch (e) {
    // silent
  }
}, CONFIG.refreshIntervalMs);

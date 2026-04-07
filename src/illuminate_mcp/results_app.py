"""Interactive Results Dashboard — MCP App HTML resource."""

# The URI used to register this app with the MCP host.
RESULTS_DASHBOARD_URI = "ui://illuminate/results-dashboard"

# CSP domains needed by the embedded app (Chart.js + ext-apps SDK from CDN).
RESULTS_DASHBOARD_CSP = {
    "resourceDomains": [
        "https://unpkg.com",
        "https://cdn.jsdelivr.net",
    ],
}


def results_dashboard_html() -> str:
    """Return the self-contained HTML for the results dashboard MCP App."""
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>Illuminate Results Dashboard</title>
<style>
/* ── Reset & base ───────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff; --bg-secondary: #f8f9fa; --bg-hover: #f0f1f3;
  --text: #1a1a2e; --text-secondary: #6c757d; --text-muted: #adb5bd;
  --border: #dee2e6; --border-focus: #6366f1;
  --accent: #6366f1; --accent-hover: #4f46e5; --accent-text: #ffffff;
  --success: #10b981; --warning: #f59e0b; --error: #ef4444;
  --chart-1: #6366f1; --chart-2: #06b6d4; --chart-3: #f59e0b;
  --chart-4: #10b981; --chart-5: #ef4444; --chart-6: #8b5cf6;
  --chart-7: #ec4899; --chart-8: #14b8a6;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --bg-secondary: #1e293b; --bg-hover: #334155;
    --text: #e2e8f0; --text-secondary: #94a3b8; --text-muted: #64748b;
    --border: #334155; --border-focus: #818cf8;
    --accent: #818cf8; --accent-hover: #6366f1; --accent-text: #0f172a;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
}

body {
  font-family: var(--font); background: var(--bg); color: var(--text);
  line-height: 1.5; padding: 16px; min-height: 100vh;
}

/* ── Layout ─────────────────────────────────────────────── */
#loading { text-align: center; padding: 48px 16px; color: var(--text-secondary); }
#loading .spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }

#dashboard { display: none; }

.toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.toolbar .summary {
  flex: 1; font-size: 14px; color: var(--text-secondary); min-width: 200px;
}
.toolbar .meta-badge {
  font-size: 11px; background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 12px; padding: 2px 10px; color: var(--text-muted); white-space: nowrap;
}

.btn-group { display: flex; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
.btn-group button {
  background: var(--bg-secondary); border: none; padding: 6px 14px;
  font-size: 13px; color: var(--text-secondary); cursor: pointer;
  border-right: 1px solid var(--border); transition: all 0.15s;
}
.btn-group button:last-child { border-right: none; }
.btn-group button:hover { background: var(--bg-hover); }
.btn-group button.active { background: var(--accent); color: var(--accent-text); font-weight: 600; }

.action-btn {
  background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 6px 12px; font-size: 13px; color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.action-btn:hover { background: var(--bg-hover); border-color: var(--accent); color: var(--accent); }

/* ── Search bar ─────────────────────────────────────────── */
.search-bar {
  margin-bottom: 12px; position: relative;
}
.search-bar input {
  width: 100%; padding: 8px 12px 8px 34px; font-size: 13px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-secondary); color: var(--text);
  outline: none; transition: border-color 0.15s;
}
.search-bar input:focus { border-color: var(--border-focus); }
.search-bar .search-icon {
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  color: var(--text-muted); font-size: 14px; pointer-events: none;
}

/* ── Table ──────────────────────────────────────────────── */
.table-container {
  overflow-x: auto; border: 1px solid var(--border);
  border-radius: var(--radius); box-shadow: var(--shadow);
}
table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
thead { position: sticky; top: 0; z-index: 1; }
th {
  background: var(--bg-secondary); padding: 10px 14px; text-align: left;
  font-weight: 600; font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.03em; color: var(--text-secondary);
  border-bottom: 2px solid var(--border); cursor: pointer;
  user-select: none; white-space: nowrap; transition: background 0.15s;
}
th:hover { background: var(--bg-hover); }
th .sort-indicator { margin-left: 4px; font-size: 10px; opacity: 0.5; }
th.sorted .sort-indicator { opacity: 1; color: var(--accent); }
td {
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  font-family: var(--mono); font-size: 12px; white-space: nowrap;
  max-width: 320px; overflow: hidden; text-overflow: ellipsis;
}
tr:hover td { background: var(--bg-hover); }
td.numeric { text-align: right; }
td.null-value { color: var(--text-muted); font-style: italic; }
td.clickable { cursor: pointer; color: var(--accent); }
td.clickable:hover { text-decoration: underline; }
td.expandable { cursor: pointer; }
td.expandable:hover { color: var(--accent); }

/* Cell popover */
.cell-popover {
  position: fixed; z-index: 200;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.18);
  width: min(420px, calc(100vw - 32px));
  max-height: min(320px, calc(100vh - 32px));
  display: flex; flex-direction: column;
  animation: popIn 0.12s ease-out;
}
@keyframes popIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
.cell-popover-header {
  display: flex; align-items: center; padding: 8px 12px;
  border-bottom: 1px solid var(--border); background: var(--bg-secondary);
  border-radius: 8px 8px 0 0; flex-shrink: 0;
}
.cell-popover-header .col-label {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.03em; color: var(--text-muted);
}
.cell-popover-header .type-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 6px;
  margin-left: 8px; font-weight: 600;
}
.type-badge.json { background: #f59e0b22; color: var(--warning); }
.type-badge.text { background: #6366f122; color: var(--accent); }
.cell-popover-header .pop-close {
  margin-left: auto; background: none; border: none; color: var(--text-muted);
  font-size: 16px; cursor: pointer; padding: 0 4px; border-radius: 4px;
}
.cell-popover-header .pop-close:hover { color: var(--text); background: var(--bg-hover); }
.cell-popover-body {
  padding: 10px 14px; overflow: auto; flex: 1; min-height: 0;
}
.cell-popover-body pre {
  font-family: var(--mono); font-size: 11px; line-height: 1.5;
  white-space: pre-wrap; word-break: break-word; margin: 0; color: var(--text);
}
.cell-popover-body pre .json-key { color: var(--accent); }
.cell-popover-body pre .json-str { color: var(--success); }
.cell-popover-body pre .json-num { color: var(--warning); }
.cell-popover-body pre .json-bool { color: #ef4444; }
.cell-popover-body pre .json-null { color: var(--text-muted); font-style: italic; }

.table-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; font-size: 12px; color: var(--text-muted);
  border-top: 1px solid var(--border); background: var(--bg-secondary);
}

/* ── Chart ──────────────────────────────────────────────── */
.chart-container {
  border: 1px solid var(--border); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 20px; background: var(--bg);
  position: relative; min-height: 300px;
}
.chart-container canvas { width: 100% !important; max-height: 400px; }

/* ── Drill-down panel ───────────────────────────────────── */
.drill-panel {
  margin-top: 12px; padding: 14px 16px; background: var(--bg-secondary);
  border: 1px solid var(--accent); border-radius: var(--radius);
  font-size: 13px; display: none; animation: slideIn 0.2s ease-out;
}
.drill-header {
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.drill-panel .label { font-weight: 600; color: var(--accent); }
.drill-panel .value { font-family: var(--mono); flex: 1; }
.drill-status {
  font-size: 11px; padding: 2px 8px; border-radius: 10px; white-space: nowrap;
}
.drill-status.ok { background: #10b98122; color: var(--success); }
.drill-status.fail { background: #ef444422; color: var(--error); }
.drill-close {
  background: none; border: none; color: var(--text-muted); font-size: 18px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.drill-close:hover { color: var(--text); }
.drill-suggestions {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;
}
.drill-suggestions button {
  background: var(--bg); border: 1px solid var(--border); border-radius: 16px;
  padding: 5px 14px; font-size: 12px; color: var(--text);
  cursor: pointer; transition: all 0.15s; max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.drill-suggestions button:hover {
  border-color: var(--accent); color: var(--accent); background: var(--bg-hover);
}
.drill-suggestions button.sent {
  border-color: var(--success); color: var(--success); background: #10b98115;
  pointer-events: none;
}
.drill-sent-banner {
  margin-top: 10px; padding: 10px 14px; background: var(--bg);
  border: 1px solid var(--success); border-radius: var(--radius);
  display: none; animation: slideIn 0.15s ease-out;
}
.drill-sent-banner .sent-label {
  display: flex; align-items: center; gap: 6px; font-size: 12px;
  color: var(--success); font-weight: 600; margin-bottom: 4px;
}
.drill-sent-banner .sent-text {
  font-family: var(--mono); font-size: 12px; color: var(--text-secondary);
  padding: 4px 0; word-break: break-word;
}
.drill-hint { color: var(--text-muted); font-size: 12px; margin-top: 8px; }
@keyframes slideIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }

/* ── Responsive ─────────────────────────────────────────── */
@media (max-width: 600px) {
  .toolbar { flex-direction: column; align-items: flex-start; }
  td { max-width: 180px; }
}
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <div>Waiting for query results&hellip;</div>
</div>

<div id="dashboard">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="summary" id="summary"></div>
    <span class="meta-badge" id="exec-time"></span>
    <div class="btn-group" id="view-toggle">
      <button data-view="table" class="active">Table</button>
      <button data-view="chart">Chart</button>
      <button data-view="both">Both</button>
    </div>
    <button class="action-btn" id="btn-csv" title="Download CSV">Export CSV</button>
  </div>

  <!-- Search -->
  <div class="search-bar" id="search-section">
    <span class="search-icon">&#128269;</span>
    <input type="text" id="search-input" placeholder="Filter rows&hellip;" />
  </div>

  <!-- Table view -->
  <div id="table-view">
    <div class="table-container">
      <table>
        <thead><tr id="table-head"></tr></thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
    <div id="scroll-sentinel" style="height:1px;"></div>
    <div class="table-footer">
      <span id="row-count"></span>
      <span id="filter-count" style="display:none"></span>
    </div>
  </div>

  <!-- Chart view -->
  <div id="chart-view" style="display:none;">
    <div class="chart-container">
      <canvas id="chart-canvas"></canvas>
    </div>
  </div>

  <!-- Drill-down -->
  <div class="drill-panel" id="drill-panel">
    <div class="drill-header">
      <span class="label">Selected:</span>
      <span class="value" id="drill-value"></span>
      <span class="drill-status" id="drill-status"></span>
      <button class="drill-close" id="drill-close" title="Dismiss">&times;</button>
    </div>
    <div class="drill-suggestions" id="drill-suggestions"></div>
    <div class="drill-sent-banner" id="drill-sent-banner">
      <div class="sent-label">&#10003; Sent to chat</div>
      <div class="sent-text" id="drill-sent-text"></div>
    </div>
    <div class="drill-hint" id="drill-hint"></div>
  </div>
</div>

<script type="module">
import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@latest/app-with-deps";

// ── State ──────────────────────────────────────────────────
let columns = [];
let allRows = [];
let filteredRows = [];
let sortCol = -1;
let sortAsc = true;
let currentView = "table";
let chartInstance = null;
let chartHint = null;
let question = "";
let normalizedSql = "";
let hostCaps = null;
const PAGE_SIZE = 50;
let renderedCount = 0;
let numericCols = new Set();
let scrollObserver = null;

// ── App init ───────────────────────────────────────────────
const app = new App({ name: "Illuminate Results Dashboard", version: "1.0.0" });

app.ontoolresult = ({ structuredContent, content }) => {
  let data = structuredContent;
  if (!data && content?.[0]?.text) {
    try { data = JSON.parse(content[0].text); } catch {}
  }
  if (data) renderDashboard(data);
};

app.ontoolinput = ({ arguments: args }) => {
  if (args?.question) question = args.question;
};

app.ontoolinputpartial = ({ arguments: args }) => {
  if (args?.question) question = args.question;
};

app.onerror = (err) => {
  log("warn", "App error: " + (err?.message || JSON.stringify(err)));
};

await app.connect();

// Cache host capabilities after connect
try { hostCaps = app.getHostCapabilities?.() ?? null; } catch { hostCaps = null; }
log("info", "Connected. Host capabilities: " + JSON.stringify(hostCaps));

async function log(level, msg) {
  try { await app.sendLog?.({ level, message: msg }); } catch { /* best effort */ }
}

// ── Render ─────────────────────────────────────────────────
function renderDashboard(data) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("dashboard").style.display = "block";

  // Extract output data
  const output = data.output || data;
  const table = output.table || {};
  columns = table.columns || [];
  allRows = (table.rows || []).map(r => Array.isArray(r) ? r : Object.values(r));
  filteredRows = [...allRows];
  chartHint = output.chart_hint || null;

  // Question and SQL from input or data
  if (data.question) question = data.question;
  if (data.normalized_sql) normalizedSql = data.normalized_sql;

  // Summary
  const summaryEl = document.getElementById("summary");
  summaryEl.textContent = output.summary_text || `${allRows.length} rows, ${columns.length} columns`;

  // Execution time
  const execEl = document.getElementById("exec-time");
  if (data.execution_seconds != null) {
    execEl.textContent = `${data.execution_seconds.toFixed(2)}s`;
  } else {
    execEl.style.display = "none";
  }

  // Detect chart availability
  const chartBtn = document.querySelector('[data-view="chart"]');
  const bothBtn = document.querySelector('[data-view="both"]');
  const canChart = columns.length >= 2 && allRows.length > 0;
  if (!canChart) {
    chartBtn.style.opacity = "0.4";
    chartBtn.style.pointerEvents = "none";
    bothBtn.style.opacity = "0.4";
    bothBtn.style.pointerEvents = "none";
  }

  // If chart hint suggests visualization, default to "both"
  if (canChart && chartHint && output.output_parts?.includes("viz")) {
    setView("both");
  }

  renderTable();
  if (canChart) renderChart();
}

// ── Table rendering (paginated with lazy load) ────────────
function renderTable() {
  const thead = document.getElementById("table-head");
  const tbody = document.getElementById("table-body");

  // Header
  thead.innerHTML = "";
  columns.forEach((col, i) => {
    const th = document.createElement("th");
    th.textContent = col;
    const indicator = document.createElement("span");
    indicator.className = "sort-indicator";
    indicator.textContent = sortCol === i ? (sortAsc ? "\u25B2" : "\u25BC") : "\u25B2";
    th.appendChild(indicator);
    if (sortCol === i) th.classList.add("sorted");
    th.addEventListener("click", () => sortByColumn(i));
    thead.appendChild(th);
  });

  // Detect numeric columns once
  numericCols = new Set();
  for (let i = 0; i < columns.length; i++) {
    if (isNumericCol(i)) numericCols.add(i);
  }

  // Reset and render first page
  tbody.innerHTML = "";
  renderedCount = 0;
  renderNextPage();
  setupScrollObserver();
}

function renderNextPage() {
  const tbody = document.getElementById("table-body");
  const end = Math.min(renderedCount + PAGE_SIZE, filteredRows.length);

  for (let ri = renderedCount; ri < end; ri++) {
    const row = filteredRows[ri];
    const tr = document.createElement("tr");
    row.forEach((val, i) => {
      const td = document.createElement("td");
      if (val === null || val === undefined) {
        td.textContent = "null";
        td.classList.add("null-value");
      } else {
        const strVal = String(val);
        td.textContent = formatValue(val, numericCols.has(i), columns[i]);
        if (numericCols.has(i)) td.classList.add("numeric");
        if (strVal.length > 30 || isJsonLike(strVal)) {
          td.classList.add("expandable");
          td.dataset.col = columns[i];
          td.dataset.row = ri;
          td.dataset.ci = i;
        }
      }
      if (i === 0 && val !== null && val !== undefined) {
        td.classList.add("clickable");
        td.addEventListener("click", () => drillDown(columns[0], val, row));
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  }

  renderedCount = end;
  updateFooter();
}

function updateFooter() {
  document.getElementById("row-count").textContent =
    `Showing ${renderedCount} of ${filteredRows.length} rows` +
    (filteredRows.length < allRows.length ? ` (${allRows.length} total)` : "");

  const filterCount = document.getElementById("filter-count");
  if (filteredRows.length < allRows.length) {
    filterCount.textContent = `Filtered: ${allRows.length - filteredRows.length} hidden`;
    filterCount.style.display = "inline";
  } else {
    filterCount.style.display = "none";
  }
}

function setupScrollObserver() {
  if (scrollObserver) scrollObserver.disconnect();
  const sentinel = document.getElementById("scroll-sentinel");
  if (!sentinel) return;

  scrollObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && renderedCount < filteredRows.length) {
      renderNextPage();
    }
  }, { rootMargin: "200px" });

  scrollObserver.observe(sentinel);
}

function isNumericCol(index) {
  let seen = false;
  for (const row of allRows.slice(0, 50)) {
    const val = row[index];
    if (val === null || val === undefined) continue;
    if (typeof val === "number") { seen = true; continue; }
    if (typeof val === "string" && !isNaN(Number(val)) && val.trim() !== "") { seen = true; continue; }
    return false;
  }
  return seen;
}

function formatValue(val, isNumeric, colName) {
  if (isNumeric && typeof val === "number") {
    // Never locale-format ID columns — display as-is
    const upper = (colName || "").toUpperCase();
    if (upper.endsWith("_ID") || upper === "PK1" || upper === "ID") return String(val);
    return Number.isInteger(val) ? val.toLocaleString() : val.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(val);
}

// ── Sorting ────────────────────────────────────────────────
function sortByColumn(index) {
  if (sortCol === index) {
    sortAsc = !sortAsc;
  } else {
    sortCol = index;
    sortAsc = true;
  }
  filteredRows.sort((a, b) => {
    let va = a[index], vb = b[index];
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va;
    va = String(va).toLowerCase();
    vb = String(vb).toLowerCase();
    return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  renderTable(); // resets pagination
}

// ── Filtering ──────────────────────────────────────────────
document.getElementById("search-input").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase().trim();
  if (!q) {
    filteredRows = [...allRows];
  } else {
    filteredRows = allRows.filter(row =>
      row.some(val => val !== null && val !== undefined && String(val).toLowerCase().includes(q))
    );
  }
  sortCol = -1;
  renderTable();
});

// ── Chart rendering ────────────────────────────────────────
async function renderChart() {
  // Dynamically load Chart.js
  if (!window.Chart) {
    const { Chart, registerables } = await import("https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.js/+esm");
    Chart.register(...registerables);
    window.Chart = Chart;
  }

  const canvas = document.getElementById("chart-canvas");
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

  const intent = chartHint?.intent || inferIntent();
  const mark = chartHint?.mark || inferMark(intent);

  // Determine axes
  const xCol = columns[0];
  const yCol = columns.length > 1 ? columns[1] : columns[0];
  const xIdx = 0;
  const yIdx = columns.length > 1 ? 1 : 0;

  // Prepare data (up to 200 rows for chart)
  const chartRows = allRows.slice(0, 200);
  const labels = chartRows.map(r => r[xIdx] != null ? String(r[xIdx]) : "");
  const values = chartRows.map(r => {
    const v = r[yIdx];
    return typeof v === "number" ? v : (v != null ? Number(v) : null);
  });

  // Multi-series: if 3+ columns and 3rd is categorical, group by it
  let datasets;
  const palette = [
    getComputedStyle(document.documentElement).getPropertyValue("--chart-1").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-2").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-3").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-4").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-5").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-6").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-7").trim(),
    getComputedStyle(document.documentElement).getPropertyValue("--chart-8").trim(),
  ];

  if (columns.length >= 3 && !isNumericCol(2) && new Set(allRows.map(r => r[2])).size <= 8) {
    // Multi-series mode
    const groups = {};
    const uniqueLabels = [...new Set(labels)];
    chartRows.forEach((r, i) => {
      const series = String(r[2] ?? "Other");
      if (!groups[series]) groups[series] = new Array(uniqueLabels.length).fill(null);
      const li = uniqueLabels.indexOf(labels[i]);
      if (li >= 0) groups[series][li] = values[i];
    });
    datasets = Object.entries(groups).map(([name, data], i) => ({
      label: name,
      data,
      backgroundColor: palette[i % palette.length] + "cc",
      borderColor: palette[i % palette.length],
      borderWidth: mark === "line" ? 2 : 1,
      fill: false,
      tension: 0.3,
    }));
    // Override labels for unique x values
    datasets._labels = uniqueLabels;
  } else {
    datasets = [{
      label: yCol,
      data: values,
      backgroundColor: values.map((_, i) => palette[i % palette.length] + "cc"),
      borderColor: values.map((_, i) => palette[i % palette.length]),
      borderWidth: mark === "line" ? 2 : 1,
      fill: false,
      tension: 0.3,
      pointRadius: mark === "point" ? 4 : 2,
    }];
  }

  const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const gridColor = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
  const tickColor = isDark ? "#94a3b8" : "#6c757d";

  chartInstance = new window.Chart(canvas, {
    type: mark === "point" ? "scatter" : (mark === "line" ? "line" : "bar"),
    data: {
      labels: datasets._labels || labels,
      datasets: datasets.map(d => { const { _labels, ...rest } = d; return rest; }),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: {
          display: datasets.length > 1,
          labels: { color: tickColor, font: { size: 12 } },
        },
        tooltip: {
          backgroundColor: isDark ? "#1e293b" : "#ffffff",
          titleColor: isDark ? "#e2e8f0" : "#1a1a2e",
          bodyColor: isDark ? "#94a3b8" : "#6c757d",
          borderColor: isDark ? "#334155" : "#dee2e6",
          borderWidth: 1,
          cornerRadius: 6,
          padding: 10,
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: tickColor, maxRotation: 45, font: { size: 11 } },
          title: { display: true, text: xCol, color: tickColor },
        },
        y: {
          grid: { color: gridColor },
          ticks: { color: tickColor, font: { size: 11 } },
          title: { display: true, text: yCol, color: tickColor },
          beginAtZero: mark === "bar",
        },
      },
      onClick: (_evt, elements) => {
        if (elements.length > 0) {
          const idx = elements[0].index;
          const row = allRows[idx];
          if (row) drillDown(columns[0], row[0], row);
        }
      },
    },
  });
}

function inferIntent() {
  const q = question.toLowerCase();
  if (/over time|trend|month|daily|weekly|yearly/.test(q)) return "trend";
  if (/distribution|histogram|spread/.test(q)) return "distribution";
  if (/correlation|relationship|vs|versus|scatter/.test(q)) return "relationship";
  return "comparison";
}

function inferMark(intent) {
  if (intent === "trend") return "line";
  if (intent === "relationship") return "point";
  return "bar";
}

// ── View toggle ────────────────────────────────────────────
document.getElementById("view-toggle").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-view]");
  if (!btn || btn.style.pointerEvents === "none") return;
  setView(btn.dataset.view);
});

function setView(view) {
  currentView = view;
  document.querySelectorAll("#view-toggle button").forEach(b => b.classList.remove("active"));
  document.querySelector(`[data-view="${view}"]`)?.classList.add("active");

  const tableEl = document.getElementById("table-view");
  const chartEl = document.getElementById("chart-view");
  const searchEl = document.getElementById("search-section");

  tableEl.style.display = (view === "table" || view === "both") ? "block" : "none";
  chartEl.style.display = (view === "chart" || view === "both") ? "block" : "none";
  searchEl.style.display = (view === "table" || view === "both") ? "block" : "none";

  if (view === "both") {
    chartEl.style.marginBottom = "16px";
  }
}

// ── CSV export ─────────────────────────────────────────────
document.getElementById("btn-csv").addEventListener("click", async () => {
  const headerLine = columns.map(c => csvEscape(c)).join(",");
  const dataLines = filteredRows.map(row =>
    row.map(v => csvEscape(v === null || v === undefined ? "" : String(v))).join(",")
  );
  const csv = [headerLine, ...dataLines].join("\n");

  try {
    await app.downloadFile({
      contents: [{
        type: "resource",
        resource: {
          uri: "illuminate-results.csv",
          mimeType: "text/csv",
          text: csv,
        },
      }],
    });
  } catch {
    // Fallback: trigger browser download
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "illuminate-results.csv";
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }
});

function csvEscape(val) {
  const s = String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

// ── Drill-down ─────────────────────────────────────────────
document.getElementById("drill-close").addEventListener("click", () => {
  document.getElementById("drill-panel").style.display = "none";
});

async function drillDown(colName, value, row) {
  const panel = document.getElementById("drill-panel");
  const drillValue = document.getElementById("drill-value");
  const statusEl = document.getElementById("drill-status");
  const suggestionsEl = document.getElementById("drill-suggestions");
  const hintEl = document.getElementById("drill-hint");

  const rowObj = {};
  columns.forEach((c, i) => { rowObj[c] = row[i]; });

  drillValue.textContent = `${colName} = ${JSON.stringify(value)}`;
  statusEl.textContent = "";
  statusEl.className = "drill-status";
  suggestionsEl.innerHTML = "";
  hintEl.textContent = "";
  panel.style.display = "block";

  // Build suggested follow-up questions
  const suggestions = buildFollowUpSuggestions(colName, value, rowObj);
  suggestions.forEach(s => {
    const btn = document.createElement("button");
    btn.textContent = s;
    btn.title = s;
    btn.addEventListener("click", () => sendFollowUp(s, colName, value, rowObj));
    suggestionsEl.appendChild(btn);
  });

  // Attempt to update model context
  const contextText =
    `User clicked a data point in the Illuminate Results Dashboard:\n` +
    `  Column: ${colName}\n` +
    `  Value: ${JSON.stringify(value)}\n` +
    `  Full row: ${JSON.stringify(rowObj)}\n` +
    (normalizedSql ? `  Original query: ${normalizedSql}\n` : "") +
    (question ? `  Original question: ${question}\n` : "") +
    `\nSuggested follow-ups the user can see:\n` +
    suggestions.map(s => `  - "${s}"`).join("\n") +
    `\n\nWhen the user sends their next message, incorporate this drill-down context. ` +
    `If they click a suggested follow-up, generate and run the appropriate query.`;

  // Hide any previous sent banner
  document.getElementById("drill-sent-banner").style.display = "none";

  try {
    await app.updateModelContext({ context: [{ type: "text", text: contextText }] });
    statusEl.textContent = "Context updated";
    statusEl.className = "drill-status ok";
    log("info", "updateModelContext succeeded for " + colName + "=" + JSON.stringify(value));
  } catch (err) {
    const msg = err?.message || String(err);
    statusEl.textContent = "";
    log("warn", "updateModelContext failed: " + msg);
  }

  hintEl.textContent = "Click a suggestion to send it as a follow-up query.";
}

function buildFollowUpSuggestions(colName, value, rowObj) {
  const displayVal = typeof value === "string" ? value : JSON.stringify(value);
  const suggestions = [];

  // Always suggest a detail drill-down
  suggestions.push(`Show me all details where ${colName} = '${displayVal}'`);

  // If there are numeric columns, suggest aggregation
  const numCols = columns.filter((_, i) => isNumericCol(i) && columns[i] !== colName);
  if (numCols.length > 0) {
    suggestions.push(`Break down ${numCols[0]} by category for ${colName} = '${displayVal}'`);
  }

  // If there's a temporal hint in the original question or columns, suggest trend
  const hasTime = columns.some(c => /date|time|month|year|term|period|week/i.test(c));
  if (hasTime) {
    suggestions.push(`Show the trend over time for ${colName} = '${displayVal}'`);
  }

  // Suggest comparison
  if (allRows.length > 1) {
    suggestions.push(`Compare '${displayVal}' against the overall average`);
  }

  return suggestions.slice(0, 4); // max 4 suggestions
}

async function sendFollowUp(text, colName, value, rowObj) {
  const banner = document.getElementById("drill-sent-banner");
  const bannerText = document.getElementById("drill-sent-text");
  const hintEl = document.getElementById("drill-hint");

  // Highlight the clicked pill
  document.querySelectorAll("#drill-suggestions button").forEach(b => b.classList.remove("sent"));
  event?.target?.closest?.("button")?.classList.add("sent");

  // Set context first so the LLM has the row data when it processes the message
  try {
    await app.updateModelContext({
      context: [{ type: "text", text:
        `Dashboard drill-down context:\n` +
        `  Selected: ${colName} = ${JSON.stringify(value)}\n` +
        `  Row: ${JSON.stringify(rowObj)}\n` +
        (normalizedSql ? `  Previous SQL: ${normalizedSql}\n` : "")
      }],
    });
  } catch { /* supplementary — sendMessage is primary */ }

  // Send the prompt directly to the chat input
  try {
    await app.sendMessage({
      role: "user",
      content: [{ type: "text", text }],
    });
    bannerText.textContent = text;
    banner.style.display = "block";
    hintEl.textContent = "";
    log("info", "sendMessage succeeded: " + text);
  } catch (err) {
    // Fallback: copy to clipboard if sendMessage isn't supported
    hintEl.textContent = "Could not send directly. Copying to clipboard instead...";
    log("warn", "sendMessage failed: " + (err?.message || err));
    try {
      await navigator.clipboard.writeText(text);
      hintEl.textContent = "Copied! Paste into the chat input and send.";
    } catch {
      hintEl.textContent = `Paste this into the chat: ${text}`;
    }
  }
}

// ── Cell popover ───────────────────────────────────────────
let activePopover = null;

function isJsonLike(s) {
  const t = s.trim();
  return (t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]"));
}

function dismissPopover() {
  if (activePopover) { activePopover.remove(); activePopover = null; }
}

document.addEventListener("click", (e) => {
  const td = e.target.closest("td.expandable");
  if (!td) { dismissPopover(); return; }
  // Don't intercept first-column drill-down clicks
  if (td.classList.contains("clickable")) return;

  if (activePopover && activePopover._td === td) { dismissPopover(); return; }
  dismissPopover();

  const col = td.dataset.col;
  const ri = parseInt(td.dataset.row);
  const ci = parseInt(td.dataset.ci);
  const row = filteredRows[ri];
  if (!row) return;
  const rawVal = row[ci];
  if (rawVal === null || rawVal === undefined) return;

  const strVal = String(rawVal);
  const isJson = isJsonLike(strVal);

  let formatted, typeLabel;
  if (isJson) {
    try {
      const parsed = JSON.parse(strVal);
      formatted = syntaxHighlight(escHtml(JSON.stringify(parsed, null, 2)));
      typeLabel = '<span class="type-badge json">JSON</span>';
    } catch {
      formatted = escHtml(strVal);
      typeLabel = '<span class="type-badge text">Text</span>';
    }
  } else {
    formatted = escHtml(strVal);
    typeLabel = '<span class="type-badge text">Text</span>';
  }

  const rect = td.getBoundingClientRect();
  const pop = document.createElement("div");
  pop.className = "cell-popover";
  pop._td = td;
  pop.innerHTML = `
    <div class="cell-popover-header">
      <span class="col-label">${escHtml(col)}</span>
      ${typeLabel}
      <button class="pop-close">&times;</button>
    </div>
    <div class="cell-popover-body">
      <pre>${formatted}</pre>
    </div>
  `;

  document.body.appendChild(pop);
  activePopover = pop;

  const popRect = pop.getBoundingClientRect();
  let top = rect.bottom + 4;
  let left = rect.left;
  if (top + popRect.height > window.innerHeight - 8) {
    top = Math.max(8, rect.top - popRect.height - 4);
  }
  if (left + popRect.width > window.innerWidth - 8) {
    left = Math.max(8, window.innerWidth - popRect.width - 8);
  }
  pop.style.top = top + "px";
  pop.style.left = left + "px";

  pop.querySelector(".pop-close").addEventListener("click", (ev) => {
    ev.stopPropagation();
    dismissPopover();
  });
  pop.addEventListener("click", (ev) => ev.stopPropagation());
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && activePopover) dismissPopover();
});

function escHtml(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}

function syntaxHighlight(json) {
  return json.replace(
    /("(?:\\.|[^"\\])*")\s*:/g,
    '<span class="json-key">$1</span>:'
  ).replace(
    /:\s*("(?:\\.|[^"\\])*")/g,
    ': <span class="json-str">$1</span>'
  ).replace(
    /:\s*(\d+\.?\d*)/g,
    ': <span class="json-num">$1</span>'
  ).replace(
    /:\s*(true|false)/g,
    ': <span class="json-bool">$1</span>'
  ).replace(
    /:\s*(null)/g,
    ': <span class="json-null">$1</span>'
  );
}
</script>
</body>
</html>"""

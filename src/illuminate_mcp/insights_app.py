"""Insights Feed — MCP App HTML resource."""

INSIGHTS_FEED_URI = "ui://illuminate/insights-feed"

INSIGHTS_FEED_CSP = {
    "resourceDomains": [
        "https://unpkg.com",
    ],
}


def insights_feed_html() -> str:
    """Return the self-contained HTML for the insights feed MCP App."""
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>Illuminate Insights Feed</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff; --bg-secondary: #f8f9fa; --bg-hover: #f0f1f3;
  --text: #1a1a2e; --text-secondary: #6c757d; --text-muted: #adb5bd;
  --border: #dee2e6; --border-focus: #6366f1;
  --accent: #6366f1; --accent-hover: #4f46e5; --accent-text: #ffffff;
  --success: #10b981; --warning: #f59e0b; --error: #ef4444; --info: #3b82f6;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  --domain-lms: #6366f1; --domain-sis: #06b6d4; --domain-tlm: #f59e0b;
  --domain-aly: #10b981; --domain-clb: #ef4444; --domain-map: #8b5cf6;
  --domain-media: #ec4899; --domain-meta: #64748b; --domain-learn: #f97316;
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

body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; padding: 16px; }

/* Loading */
#loading { text-align: center; padding: 48px 16px; color: var(--text-secondary); }
#loading .spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
#feed { display: none; }

/* Header */
.feed-header {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.feed-title { font-size: 18px; font-weight: 700; }
.feed-stats {
  display: flex; gap: 12px; margin-left: auto; font-size: 12px; color: var(--text-muted);
}
.feed-stats .stat { display: flex; align-items: center; gap: 4px; }

/* Filters */
.filter-bar {
  display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;
}
.filter-btn {
  padding: 5px 14px; font-size: 12px; font-weight: 600; border-radius: 16px;
  border: 1px solid var(--border); background: var(--bg-secondary);
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
  white-space: nowrap;
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
.filter-btn .count { opacity: 0.7; margin-left: 4px; }
.filter-sep {
  width: 1px; background: var(--border); margin: 0 4px; align-self: stretch;
}

/* Insight cards */
.insight-card {
  border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 12px; overflow: hidden; background: var(--bg);
  box-shadow: var(--shadow); transition: border-color 0.15s;
}
.insight-card:hover { border-color: var(--accent); }
.insight-card .card-stripe {
  width: 4px; position: absolute; top: 0; bottom: 0; left: 0; border-radius: var(--radius) 0 0 var(--radius);
}
.insight-card .card-body {
  padding: 14px 16px 14px 20px; position: relative;
}
.card-top {
  display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;
}
.severity-badge {
  font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 8px;
  text-transform: uppercase; letter-spacing: 0.04em;
}
.severity-badge.critical { background: #ef444422; color: var(--error); }
.severity-badge.warning { background: #f59e0b22; color: var(--warning); }
.severity-badge.info { background: #3b82f622; color: var(--info); }
.severity-badge.ok { background: #10b98122; color: var(--success); }
.domain-badge {
  font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 8px;
  border: 1px solid var(--border); color: var(--text-muted);
}
.info-icon {
  width: 18px; height: 18px; border-radius: 50%; border: 1.5px solid var(--text-muted);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-style: italic; font-family: Georgia, serif;
  color: var(--text-muted); cursor: pointer; flex-shrink: 0;
  transition: all 0.15s;
}
.info-icon:hover { border-color: var(--accent); color: var(--accent); }
.code-icon {
  width: 18px; height: 18px; border-radius: 50%; border: 1.5px solid var(--text-muted);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; font-family: var(--mono);
  color: var(--text-muted); cursor: pointer; flex-shrink: 0;
  transition: all 0.15s;
}
.code-icon:hover { border-color: var(--accent); color: var(--accent); }

.info-popover {
  position: fixed; z-index: 200;
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  padding: 12px 14px; width: min(320px, calc(100vw - 48px));
  font-size: 12px; color: var(--text-secondary); line-height: 1.6;
  animation: popIn 0.12s ease-out;
}
@keyframes popIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }
.info-popover .info-header {
  display: flex; align-items: center; margin-bottom: 6px;
}
.info-popover .info-label {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-muted);
}
.info-popover .info-close {
  margin-left: auto; background: none; border: none; color: var(--text-muted);
  font-size: 16px; cursor: pointer; padding: 0 2px; border-radius: 4px; line-height: 1;
}
.info-popover .info-close:hover { color: var(--text); background: var(--bg-hover); }
.info-popover .info-row {
  display: flex; gap: 6px; padding: 3px 0; border-bottom: 1px solid var(--border);
}
.info-popover .info-row:last-child { border-bottom: none; }
.info-popover .info-key {
  font-weight: 600; color: var(--text); white-space: nowrap; min-width: 70px;
}
.info-popover .info-val { color: var(--text-secondary); word-break: break-word; }
.info-popover pre.sql-block {
  font-family: var(--mono); font-size: 11px; line-height: 1.5;
  background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 12px; overflow-x: auto;
  white-space: pre-wrap; word-break: break-word; color: var(--text);
  max-height: 200px;
}

.card-title { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.card-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 10px; }

/* Metric display */
.card-metric {
  display: inline-flex; align-items: baseline; gap: 6px;
  background: var(--bg-secondary); padding: 6px 12px; border-radius: 6px;
  font-family: var(--mono); font-size: 13px; margin-bottom: 10px;
}
.card-metric .big-num { font-size: 20px; font-weight: 700; }
.card-metric .context { font-size: 12px; color: var(--text-muted); }
.card-metric .change {
  font-size: 12px; font-weight: 600; padding: 1px 6px; border-radius: 6px;
}
.change.up { background: #ef444418; color: var(--error); }
.change.down { background: #10b98118; color: var(--success); }
.change.neutral { background: var(--bg-hover); color: var(--text-muted); }

/* Detail rows */
.card-details {
  margin: 8px 0; border: 1px solid var(--border); border-radius: 6px;
  overflow-x: auto; font-size: 11px;
}
.card-details table { width: 100%; border-collapse: collapse; font-family: var(--mono); }
.card-details th {
  background: var(--bg-secondary); padding: 4px 8px; text-align: left;
  font-size: 10px; text-transform: uppercase; color: var(--text-muted);
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
.card-details td {
  padding: 4px 8px; border-bottom: 1px solid var(--border);
  white-space: nowrap; max-width: 180px; overflow: hidden; text-overflow: ellipsis;
}

/* Actions */
.card-actions { display: flex; gap: 8px; align-items: center; }
.dig-btn {
  background: var(--accent); color: var(--accent-text); border: none;
  border-radius: var(--radius); padding: 6px 14px; font-size: 12px;
  font-weight: 600; cursor: pointer; transition: all 0.15s;
}
.dig-btn:hover { background: var(--accent-hover); }
.dig-btn.sent { background: var(--success); pointer-events: none; }
.toggle-details {
  background: none; border: 1px solid var(--border); border-radius: var(--radius);
  padding: 5px 12px; font-size: 11px; color: var(--text-muted);
  cursor: pointer; transition: all 0.15s;
}
.toggle-details:hover { border-color: var(--accent); color: var(--accent); }

/* Empty / error states */
.all-clear {
  text-align: center; padding: 40px 20px; color: var(--text-muted);
}
.all-clear .check { font-size: 48px; margin-bottom: 8px; color: var(--success); }
.all-clear .msg { font-size: 16px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.all-clear .sub { font-size: 13px; }

/* Error details */
.errors-section {
  margin-bottom: 16px; border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden;
}
.errors-toggle {
  width: 100%; padding: 10px 16px; font-size: 12px; font-weight: 600;
  background: var(--bg-secondary); border: none; color: var(--error);
  cursor: pointer; text-align: left; transition: background 0.1s;
}
.errors-toggle:hover { background: var(--bg-hover); }
.errors-list {
  display: none; padding: 8px 16px; font-size: 12px;
}
.errors-list.open { display: block; }
.error-item {
  padding: 6px 0; border-bottom: 1px solid var(--border);
  display: flex; gap: 8px; align-items: baseline;
}
.error-item:last-child { border-bottom: none; }
.error-item .err-id { font-family: var(--mono); font-weight: 600; color: var(--text); white-space: nowrap; }
.error-item .err-domain { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.error-item .err-msg { color: var(--text-secondary); word-break: break-word; }
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <div>Scanning for insights&hellip;</div>
</div>

<div id="feed">
  <div class="feed-header">
    <div class="feed-title">Insights</div>
    <div class="feed-stats" id="feed-stats"></div>
  </div>
  <div class="filter-bar" id="filter-bar"></div>
  <div id="errors-container"></div>
  <div id="findings-list"></div>
</div>

<script type="module">
import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@latest/app-with-deps";

const DOMAIN_COLORS = {
  CDM_LMS: "var(--domain-lms)", CDM_SIS: "var(--domain-sis)",
  CDM_TLM: "var(--domain-tlm)", CDM_ALY: "var(--domain-aly)",
  CDM_CLB: "var(--domain-clb)", CDM_MAP: "var(--domain-map)",
  CDM_MEDIA: "var(--domain-media)", CDM_META: "var(--domain-meta)",
  LEARN: "var(--domain-learn)",
};

const SEVERITY_COLORS = { critical: "var(--error)", warning: "var(--warning)", info: "var(--info)", ok: "var(--success)" };

let findings = [];
let activeSeverity = "all";
let activeDomain = "all";

const app = new App({ name: "Illuminate Insights Feed", version: "1.0.0" });

app.ontoolresult = ({ structuredContent, content }) => {
  let data = structuredContent;
  if (!data && content?.[0]?.text) {
    try { data = JSON.parse(content[0].text); } catch {}
  }
  if (data) renderFeed(data);
};

await app.connect();

function renderFeed(data) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("feed").style.display = "block";

  findings = data.findings || [];

  // Stats
  const stats = document.getElementById("feed-stats");
  stats.innerHTML = `
    ${data.current_term ? `<span class="stat" style="font-weight:600">${esc(data.current_term.name)}</span>` : ""}
    <span class="stat">${findings.length} check${findings.length !== 1 ? "s" : ""}</span>
    <span class="stat">${(data.domains_scanned || []).length} domain${(data.domains_scanned || []).length !== 1 ? "s" : ""}</span>
    ${data.queries_skipped ? `<span class="stat" style="color:var(--text-muted)">${data.queries_skipped} skipped</span>` : ""}
    ${data.queries_failed ? `<span class="stat" style="color:var(--error)">${data.queries_failed} failed</span>` : ""}
    <span class="stat">${data.scan_seconds || 0}s</span>
  `;

  renderErrors(data.errors || [], data.skipped || []);
  renderFilters();
  renderFindings();
}

function renderErrors(errors, skipped) {
  const container = document.getElementById("errors-container");
  if (!errors.length && !skipped.length) { container.innerHTML = ""; return; }

  let html = "";

  if (skipped.length) {
    const skipItems = skipped.map(e => `
      <div class="error-item">
        <span class="err-id">${esc(e.query_id)}</span>
        <span class="err-domain">${esc(e.domain)}</span>
        <span class="err-msg">${esc(e.error)}</span>
      </div>
    `).join("");
    html += `
      <div class="errors-section" style="border-color:var(--border)">
        <button class="errors-toggle" id="skip-toggle" style="color:var(--text-muted)">${skipped.length} check${skipped.length !== 1 ? "s" : ""} skipped (schema not available) — click for details</button>
        <div class="errors-list" id="skip-list">${skipItems}</div>
      </div>`;
  }

  if (errors.length) {
    const errItems = errors.map(e => `
      <div class="error-item">
        <span class="err-id">${esc(e.query_id)}</span>
        <span class="err-domain">${esc(e.domain)}</span>
        <span class="err-msg">${esc(e.error)}</span>
      </div>
    `).join("");
    html += `
      <div class="errors-section">
        <button class="errors-toggle" id="err-toggle">${errors.length} check${errors.length !== 1 ? "s" : ""} failed — click for details</button>
        <div class="errors-list" id="err-list">${errItems}</div>
      </div>`;
  }

  container.innerHTML = html;

  document.getElementById("skip-toggle")?.addEventListener("click", () => {
    document.getElementById("skip-list").classList.toggle("open");
  });
  document.getElementById("err-toggle")?.addEventListener("click", () => {
    document.getElementById("err-list").classList.toggle("open");
  });
}

function renderFilters() {
  const bar = document.getElementById("filter-bar");
  const sevCounts = { all: findings.length, critical: 0, warning: 0, info: 0, ok: 0 };
  const domCounts = {};
  findings.forEach(f => {
    sevCounts[f.severity] = (sevCounts[f.severity] || 0) + 1;
    domCounts[f.domain] = (domCounts[f.domain] || 0) + 1;
  });

  let html = "";
  for (const sev of ["all", "critical", "warning", "info", "ok"]) {
    const active = activeSeverity === sev ? " active" : "";
    const label = sev === "all" ? "All" : sev.charAt(0).toUpperCase() + sev.slice(1);
    html += `<button class="filter-btn${active}" data-sev="${sev}">${label}<span class="count">${sevCounts[sev] || 0}</span></button>`;
  }
  html += '<div class="filter-sep"></div>';
  for (const [dom, count] of Object.entries(domCounts)) {
    const active = activeDomain === dom ? " active" : "";
    html += `<button class="filter-btn${active}" data-dom="${dom}" style="border-color:${DOMAIN_COLORS[dom] || "var(--border)"}">${dom}<span class="count">${count}</span></button>`;
  }
  if (activeDomain !== "all") {
    html += `<button class="filter-btn" data-dom="all" style="font-size:11px">Clear domain</button>`;
  }
  bar.innerHTML = html;

  bar.querySelectorAll("[data-sev]").forEach(btn => {
    btn.addEventListener("click", () => { activeSeverity = btn.dataset.sev; renderFilters(); renderFindings(); });
  });
  bar.querySelectorAll("[data-dom]").forEach(btn => {
    btn.addEventListener("click", () => { activeDomain = btn.dataset.dom; renderFilters(); renderFindings(); });
  });
}

function renderFindings() {
  const list = document.getElementById("findings-list");
  const filtered = findings.filter(f => {
    if (activeSeverity !== "all" && f.severity !== activeSeverity) return false;
    if (activeDomain !== "all" && f.domain !== activeDomain) return false;
    return true;
  });

  if (findings.length === 0) {
    list.innerHTML = `
      <div class="all-clear">
        <div class="check">&#10003;</div>
        <div class="msg">All clear</div>
        <div class="sub">No anomalies detected across configured domains.</div>
      </div>`;
    return;
  }

  if (filtered.length === 0) {
    list.innerHTML = `<div class="all-clear"><div class="sub">No findings match the current filters.</div></div>`;
    return;
  }

  list.innerHTML = filtered.map((f, idx) => {
    const stripeColor = SEVERITY_COLORS[f.severity] || "var(--border)";
    const domColor = DOMAIN_COLORS[f.domain] || "var(--text-muted)";

    // Metric display
    let metricHtml = "";
    if (f.metric_value != null) {
      const bigNum = typeof f.metric_value === "number" ? f.metric_value.toLocaleString() : f.metric_value;
      let ctx = "";
      if (f.comparison_value != null) {
        const comp = typeof f.comparison_value === "number" ? f.comparison_value.toLocaleString() : f.comparison_value;
        ctx = `<span class="context">of ${comp}</span>`;
      }
      let changeHtml = "";
      if (f.change_pct != null) {
        const cls = f.change_pct > 0 ? "up" : f.change_pct < 0 ? "down" : "neutral";
        const sign = f.change_pct > 0 ? "+" : "";
        changeHtml = `<span class="change ${cls}">${sign}${f.change_pct}%</span>`;
      }
      metricHtml = `<div class="card-metric"><span class="big-num">${bigNum}</span>${ctx}${changeHtml}</div>`;
    }

    // Detail rows
    let detailHtml = "";
    if (f.detail_rows && f.detail_rows.length > 0 && f.detail_columns && f.detail_columns.length > 0) {
      const thead = f.detail_columns.map(c => `<th>${esc(c)}</th>`).join("");
      const tbody = f.detail_rows.map(row =>
        `<tr>${row.map(v => `<td>${esc(v == null ? "null" : String(v))}</td>`).join("")}</tr>`
      ).join("");
      detailHtml = `
        <div class="card-details" id="details-${idx}" style="display:none">
          <table><thead><tr>${thead}</tr></thead><tbody>${tbody}</tbody></table>
        </div>`;
    }

    const hasDetails = f.detail_rows && f.detail_rows.length > 0;
    const hasData = f.severity !== "ok";

    return `
      <div class="insight-card">
        <div class="card-body" style="border-left: 4px solid ${stripeColor};">
          <div class="card-top">
            <span class="severity-badge ${f.severity}">${f.severity}</span>
            <span class="domain-badge" style="color:${domColor};border-color:${domColor}">${f.domain}</span>
            <span style="margin-left:auto;display:flex;gap:6px;">
              ${f.sql ? `<span class="code-icon" data-idx="${idx}" title="View SQL">&lt;/&gt;</span>` : ""}
              ${f.explanation ? `<span class="info-icon" data-idx="${idx}" title="What does this measure?">i</span>` : ""}
            </span>
          </div>
          <div class="card-title">${esc(f.title)}</div>
          <div class="card-desc">${esc(f.description)}</div>
          ${metricHtml}
          ${detailHtml}
          <div class="card-actions">
            ${hasData ? `<button class="dig-btn" data-idx="${idx}">Dig into this</button>` : ""}
            ${hasDetails ? `<button class="toggle-details" data-target="details-${idx}">Show data</button>` : ""}
          </div>
        </div>
      </div>`;
  }).join("");

  // Wire up buttons
  list.querySelectorAll(".dig-btn").forEach(btn => {
    btn.addEventListener("click", () => digInto(filtered[parseInt(btn.dataset.idx)], btn));
  });
  list.querySelectorAll(".toggle-details").forEach(btn => {
    btn.addEventListener("click", () => {
      const el = document.getElementById(btn.dataset.target);
      if (el) {
        const visible = el.style.display !== "none";
        el.style.display = visible ? "none" : "block";
        btn.textContent = visible ? "Show data" : "Hide data";
      }
    });
  });

  // Info icon popovers
  list.querySelectorAll(".info-icon").forEach(icon => {
    icon.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(icon.dataset.idx);
      const f = filtered[idx];
      if (!f || !f.explanation) return;
      showPopover(icon, `
        <div class="info-header">
          <span class="info-label">What this measures</span>
          <button class="info-close">&times;</button>
        </div>
        <div style="margin-bottom:8px">${esc(f.explanation)}</div>
        <div class="info-row"><span class="info-key">Source</span><span class="info-val">${esc(f.domain)}</span></div>
        <div class="info-row"><span class="info-key">Check</span><span class="info-val">${esc(f.query_id)}</span></div>
        <div class="info-row"><span class="info-key">Threshold</span><span class="info-val">${f.change_pct != null ? f.change_pct + "%" : "N/A"}</span></div>
      `);
    });
  });

  // SQL code icon popovers
  list.querySelectorAll(".code-icon").forEach(icon => {
    icon.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = parseInt(icon.dataset.idx);
      const f = filtered[idx];
      if (!f || !f.sql) return;
      const sqlHtml = `
        <div class="info-header">
          <span class="info-label">SQL Query</span>
          <button class="copy-sql-btn" style="margin-left:auto;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:3px 8px;font-size:10px;font-weight:600;color:var(--text-secondary);cursor:pointer;">Copy</button>
          <button class="info-close">&times;</button>
        </div>
        <pre class="sql-block">${esc(f.sql)}</pre>
      `;
      showPopover(icon, sqlHtml, "min(480px, calc(100vw - 48px))", f.sql);
    });
  });
}

// Shared popover positioning — uses fixed position so it escapes card overflow
function showPopover(anchor, html, width, copyText) {
  document.querySelectorAll(".info-popover").forEach(p => p.remove());
  const rect = anchor.getBoundingClientRect();
  const pop = document.createElement("div");
  pop.className = "info-popover";
  if (width) pop.style.width = width;
  pop.innerHTML = html;
  pop.addEventListener("click", (ev) => ev.stopPropagation());
  pop.querySelector(".info-close")?.addEventListener("click", (ev) => {
    ev.stopPropagation();
    pop.remove();
  });
  const copyBtn = pop.querySelector(".copy-sql-btn");
  if (copyBtn && copyText) {
    copyBtn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      try {
        await navigator.clipboard.writeText(copyText);
        copyBtn.textContent = "Copied!";
        copyBtn.style.color = "var(--success)";
        copyBtn.style.borderColor = "var(--success)";
        setTimeout(() => { copyBtn.textContent = "Copy"; copyBtn.style.color = ""; copyBtn.style.borderColor = ""; }, 2000);
      } catch {}
    });
  }
  document.body.appendChild(pop);

  // Position below-right of anchor, clamped to viewport
  const popRect = pop.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.right - popRect.width;
  if (top + popRect.height > window.innerHeight - 8) top = Math.max(8, rect.top - popRect.height - 6);
  if (left < 8) left = 8;
  pop.style.left = left + "px";
  pop.style.top = top + "px";
}

// Dismiss popovers on click outside
document.addEventListener("click", () => {
  document.querySelectorAll(".info-popover").forEach(p => p.remove());
});

async function digInto(finding, btnEl) {
  try {
    await app.updateModelContext({
      context: [{ type: "text", text:
        `Insights drill-down context:\n` +
        `  Finding: ${finding.title}\n` +
        `  Domain: ${finding.domain}\n` +
        `  Severity: ${finding.severity}\n` +
        `  Metric: ${finding.metric_value}` +
        (finding.change_pct != null ? ` (change: ${finding.change_pct}%)` : "") + `\n` +
        `  Description: ${finding.description}\n`
      }],
    });
  } catch {}

  try {
    await app.sendMessage({
      role: "user",
      content: [{ type: "text", text: finding.suggested_followup }],
    });
    btnEl.textContent = "Sent!";
    btnEl.classList.add("sent");
    setTimeout(() => { btnEl.textContent = "Dig into this"; btnEl.classList.remove("sent"); }, 2000);
  } catch {
    btnEl.textContent = "Send failed";
    setTimeout(() => { btnEl.textContent = "Dig into this"; }, 2000);
  }
}

function esc(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
</script>
</body>
</html>"""

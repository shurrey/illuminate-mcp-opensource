"""Schema Explorer — MCP App HTML resource."""

SCHEMA_EXPLORER_URI = "ui://illuminate/schema-explorer"

SCHEMA_EXPLORER_CSP = {
    "resourceDomains": [
        "https://unpkg.com",
    ],
}


def schema_explorer_html() -> str:
    """Return the self-contained HTML for the schema explorer MCP App."""
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>Illuminate Schema Explorer</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff; --bg-secondary: #f8f9fa; --bg-hover: #f0f1f3; --bg-active: #eef2ff;
  --text: #1a1a2e; --text-secondary: #6c757d; --text-muted: #adb5bd;
  --border: #dee2e6; --border-focus: #6366f1;
  --accent: #6366f1; --accent-hover: #4f46e5; --accent-text: #ffffff;
  --success: #10b981; --warning: #f59e0b;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  /* Domain colors */
  --domain-lms: #6366f1; --domain-sis: #06b6d4; --domain-tlm: #f59e0b;
  --domain-aly: #10b981; --domain-clb: #ef4444; --domain-map: #8b5cf6;
  --domain-media: #ec4899; --domain-meta: #64748b; --domain-learn: #f97316;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --bg-secondary: #1e293b; --bg-hover: #334155; --bg-active: #1e1b4b;
    --text: #e2e8f0; --text-secondary: #94a3b8; --text-muted: #64748b;
    --border: #334155; --border-focus: #818cf8;
    --accent: #818cf8; --accent-hover: #6366f1; --accent-text: #0f172a;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
}

body {
  font-family: var(--font); background: var(--bg); color: var(--text);
  line-height: 1.5;
}

/* ── Loading ────────────────────────────────────────────── */
#loading { text-align: center; padding: 48px 16px; color: var(--text-secondary); }
#loading .spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
#explorer { display: none; }
#explorer.visible { display: block; }

/* ── Global search ──────────────────────────────────────── */
.search-bar {
  padding: 12px 16px; border-bottom: 1px solid var(--border);
  background: var(--bg-secondary); flex-shrink: 0; z-index: 10;
}
.search-bar input {
  width: 100%; padding: 8px 12px 8px 34px; font-size: 13px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg); color: var(--text); outline: none;
  transition: border-color 0.15s;
}
.search-bar input:focus { border-color: var(--border-focus); }
.search-bar .icon {
  position: absolute; left: 28px; top: 50%; transform: translateY(-50%);
  color: var(--text-muted); font-size: 14px; pointer-events: none;
}
.search-results {
  display: none; padding: 8px 16px; background: var(--bg);
  border-bottom: 1px solid var(--border); max-height: 300px; overflow-y: auto;
}
.search-results .sr-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  border-radius: 6px; cursor: pointer; font-size: 13px; transition: background 0.1s;
}
.search-results .sr-item:hover { background: var(--bg-hover); }
.sr-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 8px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap;
}
.sr-badge.domain { background: var(--accent); color: var(--accent-text); }
.sr-badge.entity { background: var(--success); color: white; }
.sr-badge.column { background: var(--warning); color: white; }
.sr-name { font-weight: 500; }
.sr-context { color: var(--text-muted); font-size: 12px; margin-left: auto; }

/* ── Layout ─────────────────────────────────────────────── */
.main-layout { display: flex; }

/* ── Domain sidebar ─────────────────────────────────────── */
.domain-sidebar {
  width: 220px; min-width: 220px; border-right: 1px solid var(--border);
  background: var(--bg-secondary); overflow-y: auto; flex-shrink: 0;
}
.domain-sidebar .title {
  padding: 14px 16px 8px; font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);
}
.domain-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 16px;
  cursor: pointer; transition: all 0.1s; border-left: 3px solid transparent;
}
.domain-item:hover { background: var(--bg-hover); }
.domain-item.active { background: var(--bg-active); border-left-color: var(--accent); }
.domain-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.domain-info { flex: 1; min-width: 0; }
.domain-name { font-size: 13px; font-weight: 600; }
.domain-desc {
  font-size: 11px; color: var(--text-muted); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.domain-count {
  font-size: 11px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 1px 8px; color: var(--text-muted); flex-shrink: 0;
}

/* ── Entity list ────────────────────────────────────────── */
.entity-panel {
  flex: 1; min-width: 0;
}
.entity-header {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.entity-header .domain-label {
  font-size: 16px; font-weight: 700;
}
.entity-header .domain-description {
  font-size: 13px; color: var(--text-secondary);
}
.entity-header .refresh-badge {
  font-size: 11px; background: var(--bg-secondary); border: 1px solid var(--border);
  border-radius: 12px; padding: 2px 10px; color: var(--text-muted); margin-left: auto;
}

.entity-grid {
  padding: 16px 20px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px; align-content: start;
}

.entity-card {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 14px 16px; cursor: pointer; transition: all 0.15s;
  background: var(--bg);
}
.entity-card:hover { border-color: var(--accent); box-shadow: var(--shadow); }
.entity-card.active { border-color: var(--accent); background: var(--bg-active); }
.entity-card .name { font-size: 14px; font-weight: 700; font-family: var(--mono); }
.entity-card .desc {
  font-size: 12px; color: var(--text-secondary); margin-top: 4px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.entity-card .meta {
  display: flex; gap: 12px; margin-top: 8px; font-size: 11px; color: var(--text-muted);
}
.entity-card .meta span { display: flex; align-items: center; gap: 3px; }

/* ── Detail modal ───────────────────────────────────────── */
.detail-backdrop {
  display: none; position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.35); backdrop-filter: blur(2px);
  animation: fadeIn 0.15s ease-out;
}
.detail-backdrop.open { display: flex; align-items: flex-start; justify-content: center; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

.detail-modal {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.2);
  width: min(520px, calc(100vw - 32px)); max-height: calc(100vh - 32px);
  overflow-y: auto; position: relative;
  animation: slideUp 0.2s ease-out;
}
@keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

.detail-header {
  padding: 16px 20px; border-bottom: 1px solid var(--border);
  background: var(--bg-secondary); border-radius: 12px 12px 0 0;
  position: sticky; top: 0; z-index: 1;
}
.detail-header .entity-name {
  font-size: 18px; font-weight: 700; font-family: var(--mono);
  padding-right: 32px;
}
.detail-header .entity-desc {
  font-size: 13px; color: var(--text-secondary); margin-top: 2px;
}
.detail-header .detail-actions {
  display: flex; gap: 8px; margin-top: 12px; align-items: center;
}
.detail-header .analyze-btn {
  background: var(--accent); color: var(--accent-text); border: none;
  border-radius: var(--radius); padding: 6px 14px; font-size: 12px;
  font-weight: 600; cursor: pointer; transition: background 0.15s;
  margin-left: auto;
}
.detail-header .analyze-btn:hover { background: var(--accent-hover); }
.detail-header .analyze-btn.sent {
  background: var(--success); pointer-events: none;
}
.detail-close {
  background: none; border: none; color: var(--text-muted); font-size: 22px;
  cursor: pointer; position: absolute; right: 16px; top: 14px;
  width: 28px; height: 28px; display: flex; align-items: center;
  justify-content: center; border-radius: 6px; transition: all 0.1s;
}
.detail-close:hover { color: var(--text); background: var(--bg-hover); }

/* Tabs */
.detail-tabs {
  display: flex; border-bottom: 1px solid var(--border);
  background: var(--bg-secondary); position: sticky; top: 0; z-index: 1;
}
.detail-tabs button {
  flex: 1; padding: 10px 16px; font-size: 13px; font-weight: 600;
  background: none; border: none; border-bottom: 2px solid transparent;
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.detail-tabs button:hover { color: var(--text); background: var(--bg-hover); }
.detail-tabs button.active {
  color: var(--accent); border-bottom-color: var(--accent);
}

.detail-tab-content { display: none; }
.detail-tab-content.active { display: block; }

.detail-section {
  padding: 14px 20px; border-bottom: 1px solid var(--border);
}
.detail-section:last-child { border-bottom: none; }
.detail-section .section-title {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 10px;
}

/* Column table */
.col-table { width: 100%; font-size: 12px; }
.col-table tr { border-bottom: 1px solid var(--border); }
.col-table tr:last-child { border-bottom: none; }
.col-table td { padding: 6px 0; vertical-align: top; }
.col-table .col-name {
  font-family: var(--mono); font-weight: 600; white-space: nowrap;
  padding-right: 12px; width: 1%; color: var(--text);
}
.col-table .col-desc { color: var(--text-secondary); word-break: break-word; }
.col-table .col-name.pk { color: var(--accent); }

/* Preview data table */
.preview-table-wrap { overflow-x: auto; }
.preview-table {
  width: 100%; font-size: 11px; font-family: var(--mono);
  border-collapse: collapse;
}
.preview-table th {
  background: var(--bg-secondary); padding: 6px 10px; text-align: left;
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.03em;
  color: var(--text-muted); border-bottom: 2px solid var(--border);
  white-space: nowrap; position: sticky; top: 0;
}
.preview-table td {
  padding: 5px 10px; border-bottom: 1px solid var(--border);
  white-space: nowrap; max-width: 200px; overflow: hidden;
  text-overflow: ellipsis; color: var(--text); cursor: default;
}
.preview-table td.expandable { cursor: pointer; }
.preview-table td.expandable:hover { color: var(--accent); }
.preview-table tr:hover td { background: var(--bg-hover); }
.preview-table td.null-val { color: var(--text-muted); font-style: italic; }

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
  white-space: pre-wrap; word-break: break-word; margin: 0;
  color: var(--text);
}
.cell-popover-body pre .json-key { color: var(--accent); }
.cell-popover-body pre .json-str { color: var(--success); }
.cell-popover-body pre .json-num { color: var(--warning); }
.cell-popover-body pre .json-bool { color: #ef4444; }
.cell-popover-body pre .json-null { color: var(--text-muted); font-style: italic; }
.preview-status {
  padding: 20px; text-align: center; font-size: 12px; color: var(--text-muted);
}
.preview-status .spinner-sm {
  width: 20px; height: 20px; border: 2px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 8px;
}

/* Relationships */
.rel-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 0;
  border-bottom: 1px solid var(--border); font-size: 12px;
}
.rel-item:last-child { border-bottom: none; }
.rel-arrow { color: var(--text-muted); font-size: 14px; }
.rel-col { font-family: var(--mono); color: var(--accent); font-size: 11px; }
.rel-entity {
  font-family: var(--mono); font-weight: 600; cursor: pointer;
  color: var(--text); transition: color 0.1s;
}
.rel-entity:hover { color: var(--accent); text-decoration: underline; }
.rel-confidence {
  margin-left: auto; font-size: 10px; color: var(--text-muted);
}
.no-rels { font-size: 12px; color: var(--text-muted); font-style: italic; }

/* ── Empty state ────────────────────────────────────────── */
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; color: var(--text-muted);
  font-size: 14px; gap: 8px; padding: 40px;
}

/* ── Responsive ─────────────────────────────────────────── */
@media (max-width: 900px) {
  .main-layout { flex-direction: column; }
  .domain-sidebar { width: 100%; min-width: 0; border-right: none; border-bottom: 1px solid var(--border);
    display: flex; overflow-x: auto; overflow-y: hidden; }
  .domain-sidebar .title { display: none; }
  .domain-item { border-left: none; border-bottom: 3px solid transparent; padding: 8px 14px; white-space: nowrap; }
  .domain-item.active { border-bottom-color: var(--accent); border-left-color: transparent; }
  .domain-desc { display: none; }
  .entity-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <div>Loading schema catalog&hellip;</div>
</div>

<div id="explorer">
  <!-- Search -->
  <div class="search-bar" style="position:relative;">
    <span class="icon">&#128269;</span>
    <input type="text" id="search-input" placeholder="Search domains, entities, columns&hellip;" />
  </div>
  <div class="search-results" id="search-results"></div>

  <div class="main-layout">
    <!-- Domain sidebar -->
    <div class="domain-sidebar" id="domain-sidebar">
      <div class="title">Domains</div>
    </div>

    <!-- Entity list -->
    <div class="entity-panel" id="entity-panel">
      <div class="entity-header" id="entity-header"></div>
      <div class="entity-grid" id="entity-grid">
        <div class="empty-state">Select a domain to explore its entities</div>
      </div>
    </div>
  </div>

  <!-- Detail modal (outside layout, overlays everything) -->
  <div class="detail-backdrop" id="detail-backdrop">
    <div class="detail-modal" id="detail-modal"></div>
  </div>
</div>

<script type="module">
import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@latest/app-with-deps";

// ── State ──────────────────────────────────────────────────
let catalog = {};       // { domain: { description, entities: { name: { description, column_count } } } }
let relationships = {}; // { domain: [ { source_entity, source_column, target_entity, target_column, confidence } ] }
let entityColumns = {}; // cache: "DOMAIN.ENTITY" -> { col: desc }
let activeDomain = null;
let activeEntity = null;

const DOMAIN_COLORS = {
  CDM_LMS: "var(--domain-lms)", CDM_SIS: "var(--domain-sis)",
  CDM_TLM: "var(--domain-tlm)", CDM_ALY: "var(--domain-aly)",
  CDM_CLB: "var(--domain-clb)", CDM_MAP: "var(--domain-map)",
  CDM_MEDIA: "var(--domain-media)", CDM_META: "var(--domain-meta)",
  LEARN: "var(--domain-learn)",
};

const DOMAIN_REFRESH = {
  CDM_LMS: "Overnight", CDM_SIS: "Daily", CDM_TLM: "Every 30 min",
  CDM_ALY: "Every 12 hours", CDM_CLB: "Every 2 hours", CDM_MAP: "Every 2 hours",
  CDM_MEDIA: "Near real-time", CDM_META: "Static", LEARN: "Every 4 hours",
};

// ── App init ───────────────────────────────────────────────
const app = new App({ name: "Illuminate Schema Explorer", version: "1.0.0" });

app.ontoolresult = ({ structuredContent, content }) => {
  let data = structuredContent;
  if (!data && content?.[0]?.text) {
    try { data = JSON.parse(content[0].text); } catch {}
  }
  if (data) initExplorer(data);
};

await app.connect();

// ── Initialize ─────────────────────────────────────────────
function initExplorer(data) {
  catalog = data.catalog || {};
  relationships = data.relationships || {};

  document.getElementById("loading").style.display = "none";
  document.getElementById("explorer").classList.add("visible");

  renderDomainSidebar();

  // Auto-select first domain
  const domains = Object.keys(catalog);
  if (domains.length > 0) selectDomain(domains[0]);
}

// ── Domain sidebar ─────────────────────────────────────────
function renderDomainSidebar() {
  const sidebar = document.getElementById("domain-sidebar");
  sidebar.innerHTML = '<div class="title">Domains</div>';

  for (const [domainName, domainData] of Object.entries(catalog)) {
    const entityCount = Object.keys(domainData.entities || {}).length;
    const item = document.createElement("div");
    item.className = "domain-item" + (domainName === activeDomain ? " active" : "");
    item.innerHTML = `
      <div class="domain-dot" style="background:${DOMAIN_COLORS[domainName] || "var(--text-muted)"}"></div>
      <div class="domain-info">
        <div class="domain-name">${domainName}</div>
        <div class="domain-desc">${esc(descText(domainData.description))}</div>
      </div>
      <span class="domain-count">${entityCount}</span>
    `;
    item.addEventListener("click", () => selectDomain(domainName));
    sidebar.appendChild(item);
  }
}

function selectDomain(domainName) {
  activeDomain = domainName;
  activeEntity = null;
  document.getElementById("detail-backdrop").classList.remove("open");

  // Highlight active
  document.querySelectorAll(".domain-item").forEach(el => el.classList.remove("active"));
  const items = document.querySelectorAll(".domain-item");
  const domains = Object.keys(catalog);
  const idx = domains.indexOf(domainName);
  if (idx >= 0 && items[idx]) items[idx].classList.add("active");

  renderEntityHeader(domainName);
  renderEntityGrid(domainName);
}

// ── Entity header ──────────────────────────────────────────
function renderEntityHeader(domainName) {
  const header = document.getElementById("entity-header");
  const domainData = catalog[domainName] || {};
  const refresh = DOMAIN_REFRESH[domainName] || "";
  header.innerHTML = `
    <span class="domain-label" style="color:${DOMAIN_COLORS[domainName] || "var(--text)"}">${domainName}</span>
    <span class="domain-description">${esc(descText(domainData.description))}</span>
    ${refresh ? `<span class="refresh-badge">Refresh: ${refresh}</span>` : ""}
  `;
}

// ── Entity grid ────────────────────────────────────────────
function renderEntityGrid(domainName) {
  const grid = document.getElementById("entity-grid");
  const domainData = catalog[domainName] || {};
  const entities = domainData.entities || {};
  const domainRels = relationships[domainName] || [];

  if (Object.keys(entities).length === 0) {
    grid.innerHTML = '<div class="empty-state">No entities in this domain</div>';
    return;
  }

  grid.innerHTML = "";
  for (const [entityName, entityData] of Object.entries(entities)) {
    const colCount = entityData.column_count || 0;
    // Count unique relationships for this entity
    const relCount = new Set(
      domainRels
        .filter(r => r.source_entity === entityName && r.source_entity !== r.target_entity)
        .map(r => r.target_entity)
    ).size;

    const card = document.createElement("div");
    card.className = "entity-card" + (entityName === activeEntity ? " active" : "");
    card.innerHTML = `
      <div class="name">${entityName}</div>
      <div class="desc">${esc(descText(entityData.description))}</div>
      <div class="meta">
        <span>${colCount} columns</span>
        ${relCount > 0 ? `<span>${relCount} relationship${relCount > 1 ? "s" : ""}</span>` : ""}
      </div>
    `;
    card.addEventListener("click", (e) => selectEntity(domainName, entityName, e));
    grid.appendChild(card);
  }
}

// ── Entity detail ──────────────────────────────────────────
async function selectEntity(domainName, entityName, clickEvent) {
  // Navigate to domain if different
  if (domainName !== activeDomain) {
    selectDomain(domainName);
  }
  activeEntity = entityName;

  // Compute modal top from click position (clamped to stay in viewport)
  let clickY = 16; // default fallback
  if (clickEvent) {
    clickY = Math.max(8, Math.min(clickEvent.clientY - 20, window.innerHeight - 200));
  }

  // Highlight card
  document.querySelectorAll(".entity-card").forEach(c => c.classList.remove("active"));
  const cards = document.querySelectorAll(".entity-card");
  const entities = Object.keys((catalog[domainName] || {}).entities || {});
  const idx = entities.indexOf(entityName);
  if (idx >= 0 && cards[idx]) cards[idx].classList.add("active");

  // Show modal with loading state, then fetch columns
  renderDetailModal(domainName, entityName, null, clickY);
  const columns = await fetchEntityColumns(domainName, entityName);
  if (activeEntity === entityName && activeDomain === domainName) {
    renderDetailModal(domainName, entityName, columns, clickY);
  }
}

async function fetchEntityColumns(domainName, entityName) {
  const cacheKey = `${domainName}.${entityName}`;
  if (entityColumns[cacheKey]) return entityColumns[cacheKey];

  try {
    const result = await app.callServerTool({
      name: "describe_entity",
      arguments: { domain: domainName, entity: entityName },
    });
    // Parse structured content or text
    let data = result?.structuredContent;
    if (!data && result?.content?.[0]?.text) {
      try { data = JSON.parse(result.content[0].text); } catch {}
    }
    const cols = data?.columns || {};
    entityColumns[cacheKey] = cols;
    return cols;
  } catch {
    return {};
  }
}

function closeDetailModal() {
  document.getElementById("detail-backdrop").classList.remove("open");
  activeEntity = null;
  document.querySelectorAll(".entity-card").forEach(c => c.classList.remove("active"));
}

let previewCache = {}; // "DOMAIN.ENTITY" -> { columns, rows }
let activeTab = "schema";

function renderDetailModal(domainName, entityName, columns, topY) {
  const backdrop = document.getElementById("detail-backdrop");
  const modal = document.getElementById("detail-modal");
  const y = topY || 16;
  modal.style.marginTop = y + "px";
  modal.style.maxHeight = `calc(100vh - ${y + 16}px)`;
  const domainData = catalog[domainName] || {};
  const entityData = (domainData.entities || {})[entityName] || {};
  const domainRels = relationships[domainName] || [];

  // Get unique relationships where this entity is the source
  const entityRels = [];
  const seenTargets = new Set();
  for (const rel of domainRels) {
    if (rel.source_entity === entityName && rel.source_entity !== rel.target_entity) {
      const key = `${rel.source_column}->${rel.target_entity}.${rel.target_column}`;
      if (!seenTargets.has(key)) {
        seenTargets.add(key);
        entityRels.push(rel);
      }
    }
  }
  entityRels.sort((a, b) => b.confidence - a.confidence);

  // Build columns HTML
  let colSection;
  if (columns === null) {
    colSection = `<div class="section-title">Columns (${entityData.column_count || "..."})</div>
      <div style="color:var(--text-muted);font-size:12px;">Loading columns&hellip;</div>`;
  } else {
    const colEntries = Object.entries(columns);
    const colRows = colEntries.map(([colName, colDesc]) => {
      const isPk = colName.endsWith("_ID") || colName === "PK1";
      return `<tr>
        <td class="col-name${isPk ? " pk" : ""}">${colName}</td>
        <td class="col-desc">${esc(descText(colDesc))}</td>
      </tr>`;
    }).join("");
    colSection = `<div class="section-title">Columns (${colEntries.length})</div>
      <table class="col-table">${colRows}</table>`;
  }

  // Build relationships HTML
  let relsHtml;
  if (entityRels.length === 0) {
    relsHtml = '<div class="no-rels">No inferred relationships</div>';
  } else {
    relsHtml = entityRels.map(rel => {
      const pct = Math.round(rel.confidence * 100);
      return `<div class="rel-item">
        <span class="rel-col">${rel.source_column}</span>
        <span class="rel-arrow">&rarr;</span>
        <span class="rel-entity" data-domain="${domainName}" data-entity="${rel.target_entity}">${rel.target_entity}</span>
        <span class="rel-col">.${rel.target_column}</span>
        <span class="rel-confidence">${pct}%</span>
      </div>`;
    }).join("");
  }

  // Build preview placeholder
  const cacheKey = `${domainName}.${entityName}`;
  const cached = previewCache[cacheKey];
  let previewHtml;
  if (cached) {
    previewHtml = buildPreviewTable(cached.columns, cached.rows);
  } else {
    previewHtml = `<div class="preview-status"><div class="spinner-sm"></div>Loading preview&hellip;</div>`;
  }

  modal.innerHTML = `
    <div class="detail-header" style="position:relative;">
      <div class="entity-name" style="color:${DOMAIN_COLORS[domainName] || "var(--text)"}">${entityName}</div>
      <div class="entity-desc">${esc(descText(entityData.description))}</div>
      <div class="detail-actions">
        <button class="analyze-btn" id="analyze-btn">Analyze in chat</button>
      </div>
      <button class="detail-close" id="detail-close">&times;</button>
    </div>
    <div class="detail-tabs">
      <button data-tab="schema" class="${activeTab === "schema" ? "active" : ""}">Schema</button>
      <button data-tab="data" class="${activeTab === "data" ? "active" : ""}">Data</button>
    </div>
    <div class="detail-tab-content${activeTab === "schema" ? " active" : ""}" id="tab-schema">
      <div class="detail-section">
        ${colSection}
      </div>
      <div class="detail-section">
        <div class="section-title">Relationships (${entityRels.length})</div>
        ${relsHtml}
      </div>
    </div>
    <div class="detail-tab-content${activeTab === "data" ? " active" : ""}" id="tab-data">
      <div class="detail-section" id="preview-container">
        ${previewHtml}
      </div>
    </div>
  `;

  // Wire up tab switching
  modal.querySelectorAll(".detail-tabs button").forEach(btn => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;
      modal.querySelectorAll(".detail-tabs button").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      modal.querySelectorAll(".detail-tab-content").forEach(tc => tc.classList.remove("active"));
      modal.querySelector(`#tab-${activeTab}`)?.classList.add("active");

      // Fetch preview on first Data tab visit
      if (activeTab === "data" && !previewCache[cacheKey]) {
        fetchPreview(domainName, entityName);
      }
    });
  });

  // Wire up close
  modal.querySelector("#detail-close").addEventListener("click", closeDetailModal);

  // Wire up analyze button
  modal.querySelector("#analyze-btn").addEventListener("click", (e) => {
    analyzeEntity(domainName, entityName, e.target);
  });

  // Relationship navigation
  modal.querySelectorAll(".rel-entity").forEach(el => {
    el.addEventListener("click", (e) => {
      activeTab = "schema"; // reset to schema tab when navigating
      selectEntity(el.dataset.domain, el.dataset.entity, e);
    });
  });

  // Click backdrop to close
  backdrop.onclick = (e) => { if (e.target === backdrop) closeDetailModal(); };

  backdrop.classList.add("open");

  // Auto-fetch preview if Data tab is active or if not cached yet (prefetch)
  if (activeTab === "data" && !cached) {
    fetchPreview(domainName, entityName);
  }
}

// ── Data preview ───────────────────────────────────────────
async function fetchPreview(domainName, entityName) {
  const cacheKey = `${domainName}.${entityName}`;
  if (previewCache[cacheKey]) return;

  const sql = `SELECT * FROM ${domainName}.${entityName} LIMIT 20`;
  try {
    const result = await app.callServerTool({
      name: "run_query",
      arguments: { sql, question: `Preview ${domainName}.${entityName}`, row_limit: 20, approved: true },
    });
    let data = result?.structuredContent;
    if (!data && result?.content?.[0]?.text) {
      try { data = JSON.parse(result.content[0].text); } catch {}
    }
    const output = data?.output || {};
    const table = output.table || {};
    previewCache[cacheKey] = {
      columns: table.columns || [],
      rows: table.rows || [],
    };
  } catch (err) {
    previewCache[cacheKey] = { columns: [], rows: [], error: String(err?.message || err) };
  }

  // Re-render preview if still viewing this entity
  if (activeEntity === entityName && activeDomain === domainName) {
    const container = document.getElementById("preview-container");
    if (container) {
      const cached = previewCache[cacheKey];
      container.innerHTML = cached.error
        ? `<div class="preview-status">${esc(cached.error)}</div>`
        : buildPreviewTable(cached.columns, cached.rows);
    }
  }
}

function buildPreviewTable(cols, rows) {
  if (!cols.length) return '<div class="preview-status">No data available</div>';

  const thead = cols.map(c => `<th>${esc(c)}</th>`).join("");
  const tbody = rows.map((row, ri) => {
    const vals = Array.isArray(row) ? row : Object.values(row);
    const cells = vals.map((val, ci) => {
      if (val === null || val === undefined) return `<td class="null-val">null</td>`;
      const s = String(val);
      const colName = cols[ci] || "";
      const isId = colName.endsWith("_ID") || colName === "PK1" || colName === "ID";
      const isExpandable = s.length > 30 || isJsonLike(s);
      const cls = isExpandable ? ' class="expandable"' : "";
      const dataAttrs = isExpandable ? ` data-col="${esc(colName)}" data-row="${ri}" data-ci="${ci}"` : "";
      return `<td${cls}${dataAttrs}>${esc(s)}</td>`;
    }).join("");
    return `<tr>${cells}</tr>`;
  }).join("");

  return `<div class="preview-table-wrap">
    <table class="preview-table">
      <thead><tr>${thead}</tr></thead>
      <tbody>${tbody}</tbody>
    </table>
  </div>
  <div style="font-size:11px;color:var(--text-muted);padding:8px 0 0;">
    ${rows.length} row${rows.length !== 1 ? "s" : ""}
  </div>`;
}

function isJsonLike(s) {
  const t = s.trim();
  return (t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]"));
}

// ── Cell popover ───────────────────────────────────────────
let activePopover = null;

function dismissPopover() {
  if (activePopover) { activePopover.remove(); activePopover = null; }
}

// Delegate clicks on expandable cells
document.addEventListener("click", (e) => {
  const td = e.target.closest("td.expandable");
  if (!td) { dismissPopover(); return; }

  // Don't reopen for same cell
  if (activePopover && activePopover._td === td) { dismissPopover(); return; }
  dismissPopover();

  const col = td.dataset.col;
  const ri = parseInt(td.dataset.row);
  const ci = parseInt(td.dataset.ci);
  const cacheKey = `${activeDomain}.${activeEntity}`;
  const cached = previewCache[cacheKey];
  if (!cached) return;

  const row = cached.rows[ri];
  const vals = Array.isArray(row) ? row : Object.values(row);
  const rawVal = vals[ci];
  if (rawVal === null || rawVal === undefined) return;

  const strVal = String(rawVal);
  const isJson = isJsonLike(strVal);

  // Format content
  let formatted;
  let typeLabel;
  if (isJson) {
    try {
      const parsed = JSON.parse(strVal);
      formatted = syntaxHighlight(JSON.stringify(parsed, null, 2));
      typeLabel = '<span class="type-badge json">JSON</span>';
    } catch {
      formatted = esc(strVal);
      typeLabel = '<span class="type-badge text">Text</span>';
    }
  } else {
    formatted = esc(strVal);
    typeLabel = '<span class="type-badge text">Text</span>';
  }

  // Position popover near the cell
  const rect = td.getBoundingClientRect();
  const pop = document.createElement("div");
  pop.className = "cell-popover";
  pop._td = td;
  pop.innerHTML = `
    <div class="cell-popover-header">
      <span class="col-label">${esc(col)}</span>
      ${typeLabel}
      <button class="pop-close">&times;</button>
    </div>
    <div class="cell-popover-body">
      <pre>${formatted}</pre>
    </div>
  `;

  document.body.appendChild(pop);
  activePopover = pop;

  // Compute position: prefer below-right of cell, clamp to viewport
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

  // Stop click from immediately dismissing
  pop.addEventListener("click", (ev) => ev.stopPropagation());
});

// Dismiss on Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && activePopover) dismissPopover();
});

function syntaxHighlight(json) {
  return esc(json).replace(
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

// ── Analyze in chat ────────────────────────────────────────
async function analyzeEntity(domainName, entityName, btnEl) {
  const cacheKey = `${domainName}.${entityName}`;
  const columns = entityColumns[cacheKey] || {};
  const colNames = Object.keys(columns).slice(0, 6).join(", ") || "*";
  const prompt = `Analyze ${domainName}.${entityName} — select ${colNames} and provide insights on the data`;

  try {
    await app.updateModelContext({
      context: [{ type: "text", text:
        `User is exploring ${domainName}.${entityName} in the Schema Explorer.\n` +
        `Entity: ${descText((catalog[domainName]?.entities || {})[entityName]?.description) || entityName}\n` +
        `Columns: ${JSON.stringify(columns)}\n` +
        `Use domain_override="${domainName}" when generating SQL.`
      }],
    });
  } catch {}

  try {
    await app.sendMessage({
      role: "user",
      content: [{ type: "text", text: prompt }],
    });
    btnEl.textContent = "Sent!";
    btnEl.classList.add("sent");
    setTimeout(() => { btnEl.textContent = "Analyze in chat"; btnEl.classList.remove("sent"); }, 2000);
  } catch {
    btnEl.textContent = "Send failed";
    setTimeout(() => { btnEl.textContent = "Analyze in chat"; }, 2000);
  }
}

// ── Global search ──────────────────────────────────────────
const searchInput = document.getElementById("search-input");
const searchResults = document.getElementById("search-results");

searchInput.addEventListener("input", () => {
  const q = searchInput.value.toLowerCase().trim();
  if (!q || q.length < 2) {
    searchResults.style.display = "none";
    return;
  }

  const results = [];

  for (const [domainName, domainData] of Object.entries(catalog)) {
    // Match domain name
    if (domainName.toLowerCase().includes(q) || descText(domainData.description).toLowerCase().includes(q)) {
      results.push({ type: "domain", domain: domainName, name: domainName, context: descText(domainData.description) });
    }

    for (const [entityName, entityData] of Object.entries(domainData.entities || {})) {
      // Match entity name or description
      if (entityName.toLowerCase().includes(q) || descText(entityData.description).toLowerCase().includes(q)) {
        results.push({ type: "entity", domain: domainName, entity: entityName, name: entityName, context: domainName });
      }

      // Search cached columns if we have them
      const cached = entityColumns[`${domainName}.${entityName}`];
      if (cached) {
        for (const [colName, colDesc] of Object.entries(cached)) {
          if (colName.toLowerCase().includes(q) || descText(colDesc).toLowerCase().includes(q)) {
            results.push({ type: "column", domain: domainName, entity: entityName, name: colName, context: `${domainName}.${entityName}` });
          }
        }
      }
    }
  }

  if (results.length === 0) {
    searchResults.innerHTML = '<div class="sr-item" style="color:var(--text-muted)">No matches</div>';
  } else {
    searchResults.innerHTML = results.slice(0, 20).map(r => `
      <div class="sr-item" data-type="${r.type}" data-domain="${r.domain}" data-entity="${r.entity || ""}">
        <span class="sr-badge ${r.type}">${r.type}</span>
        <span class="sr-name">${esc(r.name)}</span>
        <span class="sr-context">${esc(r.context)}</span>
      </div>
    `).join("");
  }

  searchResults.style.display = "block";

  // Wire up clicks
  searchResults.querySelectorAll(".sr-item[data-type]").forEach(el => {
    el.addEventListener("click", () => {
      const type = el.dataset.type;
      const domain = el.dataset.domain;
      const entity = el.dataset.entity;
      searchResults.style.display = "none";
      searchInput.value = "";

      if (type === "domain") {
        selectDomain(domain);
      } else if (type === "entity" || type === "column") {
        selectEntity(domain, entity);
      }
    });
  });
});

// Close search on click outside
document.addEventListener("click", (e) => {
  if (!e.target.closest(".search-bar") && !e.target.closest(".search-results")) {
    searchResults.style.display = "none";
  }
});

// ── Utility ────────────────────────────────────────────────
function esc(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}


// Extract human-readable text from a description that may be a string or
// a structured metadata object like {text:"...", visible_ind:true, ...}
function descText(val) {
  if (val == null) return "";
  if (typeof val === "string") return val;
  if (typeof val === "object" && val.text) return String(val.text);
  if (typeof val === "object") {
    // Last resort: look for any string field that looks like a description
    for (const key of ["description", "comment", "label", "name"]) {
      if (typeof val[key] === "string" && val[key]) return val[key];
    }
  }
  return String(val);
}
</script>
</body>
</html>"""

"""SQL Viewer — MCP App HTML resource for displaying formatted, copyable SQL."""

SQL_VIEWER_URI = "ui://illuminate/sql-viewer"

SQL_VIEWER_CSP = {
    "resourceDomains": [
        "https://unpkg.com",
    ],
}


def sql_viewer_html() -> str:
    """Return the self-contained HTML for the SQL viewer MCP App."""
    return _HTML


_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<title>Illuminate SQL Viewer</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #ffffff; --bg-secondary: #f8f9fa; --bg-hover: #f0f1f3;
  --text: #1a1a2e; --text-secondary: #6c757d; --text-muted: #adb5bd;
  --border: #dee2e6; --border-focus: #6366f1;
  --accent: #6366f1; --accent-hover: #4f46e5; --accent-text: #ffffff;
  --success: #10b981; --warning: #f59e0b;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
  --radius: 8px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace;
  /* SQL syntax colors */
  --sql-keyword: #6366f1; --sql-function: #06b6d4; --sql-string: #10b981;
  --sql-number: #f59e0b; --sql-comment: #94a3b8; --sql-operator: #ec4899;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a; --bg-secondary: #1e293b; --bg-hover: #334155;
    --text: #e2e8f0; --text-secondary: #94a3b8; --text-muted: #64748b;
    --border: #334155; --border-focus: #818cf8;
    --accent: #818cf8; --accent-hover: #6366f1; --accent-text: #0f172a;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
    --sql-keyword: #818cf8; --sql-function: #22d3ee; --sql-string: #34d399;
    --sql-number: #fbbf24; --sql-comment: #64748b; --sql-operator: #f472b6;
  }
}

body { font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.5; padding: 16px; }

#loading { text-align: center; padding: 48px 16px; color: var(--text-secondary); }
#loading .spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite; margin: 0 auto 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
#viewer { display: none; }

/* Header */
.viewer-header {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border);
}
.viewer-title { font-size: 16px; font-weight: 700; }
.viewer-meta {
  font-size: 12px; color: var(--text-muted); margin-left: auto;
  display: flex; gap: 12px;
}
.viewer-meta .meta-item { display: flex; align-items: center; gap: 4px; }

/* Description */
.viewer-desc {
  font-size: 13px; color: var(--text-secondary); margin-bottom: 14px;
}

/* SQL block */
.sql-container {
  position: relative; border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
}
.sql-toolbar {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: var(--bg-secondary); border-bottom: 1px solid var(--border);
  font-size: 11px; color: var(--text-muted);
}
.sql-toolbar .lang-label {
  font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
}
.copy-btn {
  margin-left: auto; display: flex; align-items: center; gap: 5px;
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  padding: 4px 10px; font-size: 11px; font-weight: 600;
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.copy-btn:hover { border-color: var(--accent); color: var(--accent); }
.copy-btn.copied { border-color: var(--success); color: var(--success); }
.copy-btn .icon { font-size: 13px; }

.sql-body {
  padding: 16px 18px; overflow-x: auto; background: var(--bg);
}
.sql-body pre {
  font-family: var(--mono); font-size: 13px; line-height: 1.7;
  white-space: pre-wrap; word-break: break-word; margin: 0;
  color: var(--text);
}
/* Syntax classes */
.sql-body .kw { color: var(--sql-keyword); font-weight: 600; }
.sql-body .fn { color: var(--sql-function); }
.sql-body .str { color: var(--sql-string); }
.sql-body .num { color: var(--sql-number); }
.sql-body .cmt { color: var(--sql-comment); font-style: italic; }
.sql-body .op { color: var(--sql-operator); }

/* Actions */
.viewer-actions {
  display: flex; gap: 8px; margin-top: 14px;
}
.action-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; font-size: 13px; font-weight: 600;
  border-radius: var(--radius); cursor: pointer; transition: all 0.15s;
}
.run-btn {
  background: var(--accent); color: var(--accent-text); border: none;
}
.run-btn:hover { background: var(--accent-hover); }
.run-btn.sent { background: var(--success); pointer-events: none; }
.edit-btn {
  background: var(--bg-secondary); color: var(--text-secondary);
  border: 1px solid var(--border);
}
.edit-btn:hover { border-color: var(--accent); color: var(--accent); }
</style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <div>Loading query&hellip;</div>
</div>

<div id="viewer">
  <div class="viewer-header">
    <div class="viewer-title" id="title"></div>
    <div class="viewer-meta" id="meta"></div>
  </div>
  <div class="viewer-desc" id="desc"></div>
  <div class="sql-container">
    <div class="sql-toolbar">
      <span class="lang-label">SQL</span>
      <button class="copy-btn" id="copy-btn">
        <span class="icon">&#128203;</span>
        <span class="label">Copy</span>
      </button>
    </div>
    <div class="sql-body">
      <pre id="sql-code"></pre>
    </div>
  </div>
  <div class="viewer-actions" id="actions"></div>
</div>

<script type="module">
import { App } from "https://unpkg.com/@modelcontextprotocol/ext-apps@latest/app-with-deps";

let rawSql = "";

const app = new App({ name: "Illuminate SQL Viewer", version: "1.0.0" });

app.ontoolresult = ({ structuredContent, content }) => {
  let data = structuredContent;
  if (!data && content?.[0]?.text) {
    try { data = JSON.parse(content[0].text); } catch {}
  }
  if (data) renderViewer(data);
};

await app.connect();

function renderViewer(data) {
  document.getElementById("loading").style.display = "none";
  document.getElementById("viewer").style.display = "block";

  rawSql = data.sql || "";
  const title = data.title || "Generated SQL";
  const description = data.description || "";
  const domain = data.domain || "";
  const confidence = data.confidence;
  const complexity = data.complexity || "";

  document.getElementById("title").textContent = title;
  document.getElementById("desc").textContent = description;

  // Meta badges
  const metaEl = document.getElementById("meta");
  let metaHtml = "";
  if (domain) metaHtml += `<span class="meta-item">${esc(domain)}</span>`;
  if (complexity) metaHtml += `<span class="meta-item">${esc(complexity)}</span>`;
  if (confidence != null) metaHtml += `<span class="meta-item">${Math.round(confidence * 100)}% confidence</span>`;
  metaEl.innerHTML = metaHtml;

  // Render highlighted SQL
  document.getElementById("sql-code").innerHTML = highlightSql(rawSql);

  // Actions
  const actions = document.getElementById("actions");
  actions.innerHTML = `
    <button class="action-btn run-btn" id="run-btn">Run this query</button>
    <button class="action-btn edit-btn" id="edit-btn">Edit and run</button>
  `;

  document.getElementById("run-btn").addEventListener("click", async (e) => {
    const btn = e.target.closest(".run-btn");
    try {
      await app.sendMessage({
        role: "user",
        content: [{ type: "text", text: `Run this query:\n\`\`\`sql\n${rawSql}\n\`\`\`` }],
      });
      btn.textContent = "Sent!";
      btn.classList.add("sent");
      setTimeout(() => { btn.textContent = "Run this query"; btn.classList.remove("sent"); }, 2000);
    } catch { btn.textContent = "Send failed"; setTimeout(() => { btn.textContent = "Run this query"; }, 2000); }
  });

  document.getElementById("edit-btn").addEventListener("click", async () => {
    try {
      await app.sendMessage({
        role: "user",
        content: [{ type: "text", text: `I'd like to modify this query before running it:\n\`\`\`sql\n${rawSql}\n\`\`\`\nPlease suggest what I might want to change.` }],
      });
    } catch {}
  });
}

// Copy button
document.getElementById("copy-btn").addEventListener("click", async () => {
  const btn = document.getElementById("copy-btn");
  try {
    await navigator.clipboard.writeText(rawSql);
    btn.querySelector(".label").textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => { btn.querySelector(".label").textContent = "Copy"; btn.classList.remove("copied"); }, 2000);
  } catch {
    // Fallback
    const ta = document.createElement("textarea");
    ta.value = rawSql;
    ta.style.cssText = "position:fixed;left:-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    btn.querySelector(".label").textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => { btn.querySelector(".label").textContent = "Copy"; btn.classList.remove("copied"); }, 2000);
  }
});

// SQL syntax highlighting
function highlightSql(sql) {
  // Escape HTML first
  let s = esc(sql);

  // Comments
  s = s.replace(/(--[^\n]*)/g, '<span class="cmt">$1</span>');

  // Strings
  s = s.replace(/('(?:[^'\\]|\\.)*')/g, '<span class="str">$1</span>');

  // Numbers
  s = s.replace(/\b(\d+\.?\d*)\b/g, '<span class="num">$1</span>');

  // Keywords
  const keywords = [
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "IS", "NULL",
    "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "ON", "AS",
    "GROUP", "BY", "ORDER", "ASC", "DESC", "HAVING", "LIMIT", "OFFSET",
    "UNION", "ALL", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE", "END",
    "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "TABLE",
    "WITH", "TRUE", "FALSE", "BETWEEN", "LIKE", "EXISTS", "ANY",
    "INTO", "VALUES", "SET", "TOP", "OVER", "PARTITION", "ROWS",
  ];
  const kwPattern = new RegExp(`\\b(${keywords.join("|")})\\b`, "gi");
  s = s.replace(kwPattern, (m) => `<span class="kw">${m}</span>`);

  // Functions
  const functions = [
    "COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "NULLIF",
    "DATE_TRUNC", "DATEADD", "DATEDIFF", "CURRENT_DATE", "CURRENT_TIMESTAMP",
    "ROUND", "CAST", "CONVERT", "NVL", "IFF", "IFNULL", "COUNT_IF",
    "ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD",
    "UPPER", "LOWER", "TRIM", "SUBSTRING", "LENGTH", "CONCAT",
  ];
  const fnPattern = new RegExp(`\\b(${functions.join("|")})\\s*(?=\\()`, "gi");
  s = s.replace(fnPattern, (m) => `<span class="fn">${m}</span>`);

  return s;
}

function esc(text) {
  const el = document.createElement("span");
  el.textContent = text;
  return el.innerHTML;
}
</script>
</body>
</html>"""

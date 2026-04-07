# Illuminate MCP Server Design

## Objective
Build a local-first MCP server that allows chat clients to query Anthology Illuminate data in Snowflake across multiple CDM domains, using metadata-grounded SQL planning constrained by a strict read-only safety policy, with interactive MCP App dashboards rendered inline in the conversation.

## Scope
- Transport: local `stdio` only (Content-Length framed, ndjson fallback)
- Data scope: 9 CDM domains (LMS, SIS, TLM, ALY, CLB, MAP, MEDIA, META) plus opt-in LEARN schema
- Querying: metadata-grounded SQL generation, refinable by the client LLM
- Interactive UI: MCP Apps for results dashboards, schema exploration, insights, and SQL viewing
- Runtime state: ephemeral (session-scoped), with optional feedback persistence
- Output: adaptive response with text summary, table data, and chart hints

## Core Design Decisions
1. Query execution does not require server-side confirmation by default — the MCP client provides its own tool approval UI.
2. Users can toggle confirmation via `set_session_approval` if their deployment requires it.
3. All Snowflake connectivity and limits are configured by the operator; no hardcoded institution details.
4. Domain routing auto-detects by question keywords, with user override and first-allowed-domain fallback.
5. Monthly credit budget is configurable with threshold warnings.
6. LEARN schema is opt-in via `ENABLE_LEARN_SCHEMA`.
7. SQL planning is metadata-driven (no server-side LLM API key required).
8. Builtin metadata catalog ships with all domains; Snowflake introspection overrides when enabled. Empty domains are auto-excluded.
9. MCP Apps are used for all user-facing data display — the LLM uses text-only tools (`run_query`) for its own analysis.
10. The query optimizer runs automatically and never blocks execution on failure.

## MCP Apps Architecture

The server uses the [MCP Apps extension](https://modelcontextprotocol.io/extensions/apps/overview) to render interactive UI inline in the conversation.

### Data flow
```
User asks question
    |
    v
LLM calls run_query (no UI) ──> analyzes data
    |
    v
LLM calls display_query (UI) ──> host renders Results Dashboard in iframe
    |                                    |
    v                                    v
LLM provides commentary        User interacts: sort, filter, drill-down
                                    |
                                    v
                              App calls sendMessage ──> triggers follow-up
                              App calls callServerTool ──> fetches more rows
```

### App ↔ Server communication
- **`ontoolresult`**: host pushes the tool result (first page of data) to the app
- **`callServerTool`**: app fetches additional pages via `get_result_page`, entity details via `describe_entity`
- **`sendMessage`**: app sends drill-down follow-ups and "Query this entity" prompts to the chat
- **`updateModelContext`**: app provides background context about user selections

### Tool ↔ UI binding
| Tool | UI Resource | Purpose |
|------|-------------|---------|
| `display_query` | `ui://illuminate/results-dashboard` | Interactive data table + chart |
| `open_schema_explorer` | `ui://illuminate/schema-explorer` | Domain/entity browser |
| `discover_insights` | `ui://illuminate/insights-feed` | Health dashboard with anomaly cards |
| `display_sql` | `ui://illuminate/sql-viewer` | Syntax-highlighted SQL |
| `run_query` | (none) | Data returned to LLM only |
| `get_result_page` | (none, app-only) | Pagination rows for dashboard |

### Payload optimization
- `display_query` sends only the first 100 rows — the app fetches more via `get_result_page`
- Chart data duplication removed — only chart hints (intent + mark type) are sent; app builds charts from table rows
- `content[0].text` for display tools is a brief summary, not a full JSON dump
- 5,000 rows: ~4MB → ~5KB in the tool response (98% reduction)

## Tool Surface (19 tools)
- **Schema:** `open_schema_explorer`, `list_domains`, `list_entities`, `describe_entity`
- **Planning:** `plan_query`, `generate_sql`, `refine_sql`, `explain_query`
- **Execution:** `run_query`, `start_query`, `get_query_status`, `get_query_results`, `get_result_page`
- **Display:** `display_query`, `display_sql`
- **Analytics:** `discover_insights`
- **Governance:** `get_planner_feedback`, `set_session_approval`, `get_budget_status`

## Resource Surface
- `illuminate://settings/runtime` - Non-secret runtime config
- `illuminate://metadata/catalog` - Full metadata snapshot
- `illuminate://metadata/status` - Introspection source and warnings
- `illuminate://metadata/entities/{domain}` - Domain entity listing
- `illuminate://metadata/entity/{domain}/{entity}` - Single entity detail
- `ui://illuminate/results-dashboard` - Results Dashboard MCP App
- `ui://illuminate/schema-explorer` - Schema Explorer MCP App
- `ui://illuminate/insights-feed` - Insights Feed MCP App
- `ui://illuminate/sql-viewer` - SQL Viewer MCP App

## Safety Model
- Allow only `SELECT` and CTE (`WITH ... SELECT`) query forms
- Block DDL, DML, multi-statement execution, and comments
- Enforce schema and table allowlists
- Per-query row limits and statement timeouts
- Optional per-query confirmation (off by default)
- Credit budget tracking with threshold warnings
- Query optimizer with EXPLAIN pre-check for large scan warnings

## Query Optimizer
Runs automatically in `_prepare_query` before every `run_query` and `display_query`:
1. **Term scoping** — injects date filter for current term when temporal columns are present
2. **Smart LIMIT** — infers appropriate limit from question intent (25–5000)
3. **EXPLAIN pre-check** — warns on scans >10M rows or >500 partitions
4. **Simplification** — flags SELECT *, adds missing LIMIT
5. **Safety wrapper** — never blocks execution on optimizer failure

## Insights Engine
`discover_insights` runs 10 diagnostic queries scoped to the current academic term (resolved from `CDM_LMS.TERM`):
- Anomaly detection via threshold comparison, period-over-period, ratio analysis, distribution patterns, and volume checks
- Findings ranked by severity (critical > warning > info > ok)
- Missing schemas classified as "skipped" not "failed"
- Each finding includes explanation, SQL source, and drill-down follow-up

## Module Overview

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI entrypoint, .env loading |
| `mcp_server.py` | JSON-RPC dispatch, capabilities, UI resource serving |
| `stdio.py` | Content-Length framed stdio transport |
| `config.py` | Environment-backed configuration with validation |
| `metadata.py` | Builtin catalog + Snowflake introspection + empty domain filtering |
| `domain_router.py` | Question-to-domain keyword routing |
| `semantic_model.py` | Entity/relationship graph for join inference |
| `planner.py` | Metadata-grounded SQL generation |
| `refinement.py` | Candidate scoring, refinement, probe profiling, diagnostics |
| `tokens.py` | Shared tokenization utilities |
| `policy.py` | Read-only SQL validation |
| `execution.py` | Snowflake query executor |
| `snowflake_conn.py` | Shared Snowflake connection factory |
| `output.py` | Adaptive output composition (text, table, chart hints) |
| `query_optimizer.py` | Pre-execution query optimization (term scoping, limits, EXPLAIN) |
| `tool_handlers.py` | Tool registry and handler dispatch |
| `session.py` | Ephemeral session state |
| `budget.py` | Credit budget tracking |
| `feedback.py` | Planner feedback with optional persistence |
| `async_jobs.py` | In-memory async job manager with TTL |
| `insights.py` | Diagnostic query catalog and anomaly detection |
| `results_app.py` | Results Dashboard MCP App HTML |
| `schema_explorer_app.py` | Schema Explorer MCP App HTML |
| `insights_app.py` | Insights Feed MCP App HTML |
| `sql_viewer_app.py` | SQL Viewer MCP App HTML |
| `exceptions.py` | Exception hierarchy |

## Extensibility
- Domain definitions are data-driven — add new domains to the builtin catalog in `metadata.py`
- Domain routing keywords are configurable in `domain_router.py`
- Snowflake introspection discovers tables/columns dynamically when enabled
- Diagnostic queries in `insights.py` are a simple catalog — add new checks by appending to `_CATALOG`
- MCP App HTML is self-contained per module — add new apps by creating a `*_app.py` module
- Policy plugin points for future privacy and compliance controls

## Non-Goals (Current)
- HTTP deployment / auth flows
- Persistent query history
- Full privacy policy enforcement (PII masking deferred)
- Server-side LLM API calls

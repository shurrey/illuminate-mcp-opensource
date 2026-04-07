# Illuminate MCP Server

Local-first MCP server for querying Anthology Illuminate data in Snowflake, with interactive MCP App dashboards that render directly in the conversation.

## Features
- Local `stdio` transport (Content-Length framed, with ndjson fallback)
- **MCP Apps** — interactive UI components (dashboards, schema explorer, insights feed, SQL viewer) rendered inline in the conversation via the MCP Apps extension
- 9 CDM domains with builtin metadata catalog, extensible via Snowflake introspection
- Optional LEARN schema support (Blackboard Open Database Schema, Premium tier)
- Read-only SQL policy with schema/table allowlists
- Metadata-grounded SQL planning without server-side LLM credentials
- **Query optimizer** — automatic term scoping, smart LIMIT inference, EXPLAIN pre-check for large scans
- **Insights engine** — automated diagnostic queries with anomaly detection, term-scoped to current academic period
- Adaptive response payloads: summary text, table data, chart hints
- Budget tracking with configurable credit thresholds
- Async query execution for long-running jobs
- Paginated results — dashboard fetches additional rows on scroll via `get_result_page`
- Planner feedback loop with optional persistence

## MCP Apps

This server uses the [MCP Apps extension](https://modelcontextprotocol.io/extensions/apps/overview) to render interactive UI components directly inside the AI conversation. MCP Apps are supported by Claude Desktop, ChatGPT, VS Code Copilot, and other MCP-compatible hosts.

### Available Apps

| App | Tool | Description |
|-----|------|-------------|
| **Results Dashboard** | `display_query` | Interactive table with sorting, filtering, pagination, Chart.js visualization, CSV export, drill-down with follow-up suggestions, cell popovers for JSON/long text |
| **Schema Explorer** | `open_schema_explorer` | Browse domains, entities, columns, and relationships. Modal detail view with Data preview tab. "Analyze in chat" sends queries via `sendMessage` |
| **Insights Feed** | `discover_insights` | Automated health dashboard — 10 diagnostic checks across CDM domains, term-scoped, severity-ranked cards with "Dig into this" drill-down |
| **SQL Viewer** | `display_sql` | Syntax-highlighted SQL display with copy button, "Run this query" and "Edit and run" actions |

### How MCP Apps work

1. Tools declare a `_meta.ui.resourceUri` pointing to a `ui://` HTML resource
2. When the host calls a tool with UI binding, it fetches the HTML and renders it in a sandboxed iframe
3. The app receives tool results via `ontoolresult` and renders the interactive UI
4. The app can call server tools via `callServerTool` (e.g., paginated data fetch, entity details)
5. The app can send messages to the chat via `sendMessage` (e.g., drill-down follow-ups)
6. The app can update model context via `updateModelContext` for background context

### Tool selection rules

The server instructs the LLM to use tools in this order:

1. **`run_query`** — default for ALL data gathering and analysis. Returns data to the LLM with no UI rendered.
2. **`display_query`** — ONLY after analysis is complete and the user should see an interactive dashboard. Re-runs the same SQL (Snowflake caches results, so re-execution is instant and free).
3. **`display_sql`** — when the user asks to see or review a generated SQL query.
4. **`discover_insights`** — when the user asks for anomalies, red flags, or what they should look at.
5. **`open_schema_explorer`** — ONLY when the user explicitly asks to browse the schema.

## Supported domains

| Domain | Description | Refresh Rate |
|--------|-------------|-------------|
| **CDM_LMS** | Learning Management System (courses, grades, enrollments, assignments) | Overnight |
| **CDM_SIS** | Student Information System (students, terms, programs, registrations) | Daily |
| **CDM_TLM** | Teaching & Learning Metadata (telemetry, activity events, Ultra events) | Every 30 min |
| **CDM_ALY** | Analytics (course scores, content scores, accessibility) | Every 12 hours |
| **CDM_CLB** | Collaborate (virtual classroom sessions, attendance, recordings) | Every 2 hours |
| **CDM_MAP** | Cross-system mapping (user and course identity linking) | Every 2 hours |
| **CDM_MEDIA** | Video Studio (media content, viewing activity) | Near real-time |
| **CDM_META** | Metadata (data sources, instance reference data) | Static |
| **LEARN** | Blackboard Learn Open Database Schema (Premium only, opt-in) | Every 4 hours |

## Quick start

**Requirements:** Python 3.12+ (use `pyenv` recommended)

```bash
# 1. Clone and enter the repo
cd illuminate-mcp

# 2. Set Python version
pyenv local 3.12.12

# 3. Install package
python -m pip install -e .

# 4. Install Snowflake connector (required for live queries)
python -m pip install -r requirements-snowflake.txt

# 5. Configure environment
cp .env.example .env
# Edit .env with your Snowflake credentials and desired settings

# 6. Run tests
PYTHONPATH=src python -m unittest discover -s tests -v

# 7. Start the server
illuminate-mcp
```

The server automatically loads `.env` from the project directory on startup — no manual env sourcing needed.

## Configuration

All configuration is via environment variables in `.env`. See `.env.example` for the full template with comments.

### Snowflake credentials
Required when `ENABLE_QUERY_EXECUTION=true` or `ENABLE_METADATA_INTROSPECTION=true`:
- `SNOWFLAKE_ACCOUNT` - Account identifier (URL prefix is stripped automatically)
- `SNOWFLAKE_USER` - Service account username
- `SNOWFLAKE_PASSWORD` - Service account password
- `SNOWFLAKE_ROLE` - Query execution role
- `SNOWFLAKE_WAREHOUSE` - Compute warehouse
- `SNOWFLAKE_DATABASE` - Target database

### Domain and schema allowlists
- `ALLOWED_DOMAINS` - Comma-separated CDM domains to expose (default: `CDM_LMS,CDM_TLM,CDM_ALY`)
- `ALLOWED_SCHEMAS` - Comma-separated schemas for policy enforcement (should match domains)
- `ALLOWED_TABLES` - Optional table-level allowlist (empty = all tables in allowed schemas)

Domains with no tables in Snowflake are automatically excluded when metadata introspection is enabled.

### LEARN schema (opt-in)
The LEARN schema provides access to 191+ raw Blackboard Learn source tables. It requires Illuminate Premium tier.

```bash
ENABLE_LEARN_SCHEMA=true
```

When enabled, `LEARN` is automatically added to `ALLOWED_DOMAINS` and `ALLOWED_SCHEMAS`.

### Feature flags
| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_QUERY_EXECUTION` | `false` | Allow SQL execution against Snowflake |
| `ENABLE_METADATA_INTROSPECTION` | `false` | Load schema from Snowflake instead of builtin catalog |
| `ENABLE_PLANNER_PROBES` | `false` | Preflight SQL candidates for non-empty results |
| `ENABLE_PERSISTENT_FEEDBACK` | `false` | Persist planner feedback to disk |
| `ENABLE_LEARN_SCHEMA` | `false` | Include LEARN schema (Premium only) |

### Runtime limits
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_ROWS` | `1000` | Maximum rows returned per query |
| `STATEMENT_TIMEOUT_SECONDS` | `120` | Snowflake statement timeout |
| `REQUIRE_QUERY_CONFIRMATION` | `false` | Require `approved=true` per query (MCP client already provides tool approval) |
| `DEFAULT_SESSION_APPROVAL_MODE` | `per-query` | `per-query` or `approve-all` |

### Budget governance
| Variable | Default | Description |
|----------|---------|-------------|
| `MONTHLY_CREDIT_BUDGET` | `100` | Monthly Snowflake credit limit |
| `BUDGET_WARNING_THRESHOLDS` | `70,85,100` | Warning percentages |
| `WAREHOUSE_CREDITS_PER_HOUR` | `0` | Fallback credit estimate rate |

### Output shaping
| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_OUTPUT_MODE` | `auto` | `auto`, `text`, `table`, or `viz` |
| `MAX_TEXT_SUMMARY_LENGTH` | `1200` | Maximum summary text length |

## MCP tools

### Query tools
| Tool | UI | Description |
|------|----|-------------|
| `run_query` | No | Execute SQL and return results as data (default for all data gathering) |
| `display_query` | **Results Dashboard** | Execute SQL and display interactive dashboard (only for final presentation) |
| `display_sql` | **SQL Viewer** | Display formatted SQL with syntax highlighting and copy button |
| `start_query` | No | Start async query execution, returns job ID |
| `get_query_status` | No | Poll async job status |
| `get_query_results` | No | Retrieve completed async job results |
| `get_result_page` | No (app-only) | Fetch paginated rows for dashboard lazy loading |

### Schema tools
| Tool | UI | Description |
|------|----|-------------|
| `open_schema_explorer` | **Schema Explorer** | Interactive visual schema browser (only on explicit user request) |
| `list_domains` | No | List configured CDM domains |
| `list_entities` | No | List entities in a domain |
| `describe_entity` | No | Describe entity schema with column definitions |

### Planning tools
| Tool | Description |
|------|-------------|
| `plan_query` | Generate multiple ranked SQL candidates with confidence/complexity |
| `generate_sql` | Return recommended SQL (strict + fallback) from plan_query |
| `refine_sql` | Refine a failed query into strict and fallback retry candidates |
| `explain_query` | Validate SQL against read-only policy |

### Analytics tools
| Tool | UI | Description |
|------|----|-------------|
| `discover_insights` | **Insights Feed** | Automated diagnostic scan across configured domains |

### Governance tools
| Tool | Description |
|------|-------------|
| `get_planner_feedback` | Inspect execution feedback statistics |
| `set_session_approval` | Switch approval mode (`per-query` / `approve-all`) |
| `get_budget_status` | Check budget tracking status |

## MCP resources

| URI | Description |
|-----|-------------|
| `illuminate://settings/runtime` | Current non-secret runtime configuration |
| `illuminate://metadata/catalog` | Full domain and entity metadata snapshot |
| `illuminate://metadata/status` | Metadata source and fallback warnings |
| `illuminate://metadata/entities/{domain}` | Entity listing for a domain |
| `illuminate://metadata/entity/{domain}/{entity}` | Single entity detail |
| `ui://illuminate/results-dashboard` | Results Dashboard MCP App HTML |
| `ui://illuminate/schema-explorer` | Schema Explorer MCP App HTML |
| `ui://illuminate/insights-feed` | Insights Feed MCP App HTML |
| `ui://illuminate/sql-viewer` | SQL Viewer MCP App HTML |

## Query optimizer

The query optimizer runs automatically before every `run_query` and `display_query` execution:

1. **Term scoping** — if the query touches a table with a temporal column and the question doesn't ask for historical/trend data, a current-term date filter is injected automatically (~120 days)
2. **Smart LIMIT** — non-aggregate queries without a LIMIT get one inferred from the question intent (25 for previews, 200 for lists, 500 for investigations, 5000 for "all")
3. **EXPLAIN pre-check** — estimates scan size before execution and warns if >10M rows or >500 partitions
4. **SELECT * hint** — flags queries using `SELECT *` for potential column reduction
5. **Safety wrapper** — the optimizer never blocks execution; if it fails, the original SQL runs unchanged

Applied optimizations are returned in `optimizations_applied` and warnings in `optimization_warnings` in the query response.

## Insights engine

`discover_insights` runs 10 diagnostic queries across configured CDM domains:

- **CDM_LMS**: Enrollment trend, zero-activity courses, low normalized scores, attempt completion, low instructor activity
- **CDM_TLM**: Telemetry event volume
- **CDM_ALY**: Course accessibility score distribution, stale content scores
- **CDM_SIS**: Enrollment trend, student status distribution

Queries are scoped to the **current academic term** (resolved from `CDM_LMS.TERM`). Findings are severity-ranked (critical/warning/info/ok) with threshold-based anomaly detection. Each insight card includes:
- Severity badge and domain tag
- Metric display with change percentage
- Info icon with explanation of what the check measures
- SQL icon showing the exact query that ran
- "Dig into this" button that sends a follow-up query via `sendMessage`

Errors from missing schemas are classified as "skipped" (not "failed") for clean UX.

## MCP prompts

| Prompt | Description |
|--------|-------------|
| `explore_lms_entities` | Guided exploration of LMS schema |
| `build_enrollment_trend_query` | Guided enrollment trend analysis (optional `term` parameter) |

## Query planning workflow
1. Use `plan_query` to get multiple ranked SQL candidates
2. `generate_sql` returns the top recommended candidate
3. Execute with `run_query` (sync) or `start_query` (async)
4. If no data returned, check `no_data_diagnostics.refinement_candidates` in the response
5. Use `refine_sql` to get retry candidates for failed queries
6. Use `get_planner_feedback` to inspect execution history influencing rankings

## MCP compatibility
- Supports MCP Apps extension (SEP-1865, spec `2026-01-26`) for inline interactive UI
- Supports `prompts/list` and `prompts/get` for clients that resolve prompt payloads explicitly
- Tool execution failures are returned as `tools/call` results with `isError=true`
- Supports Content-Length framed stdio (default) and ndjson mode (`MCP_STDIO_MODE=ndjson`)

## Run tests
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Operations
See [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) for startup checks, troubleshooting, and incident handling.

## Architecture
See [DESIGN.md](DESIGN.md) for design decisions and system architecture.

# Illuminate MCP Server

Local-first MCP server for querying Anthology Illuminate data in Snowflake.

## Features
- Local `stdio` transport (Content-Length framed, with ndjson fallback)
- 9 CDM domains with builtin metadata catalog, extensible via Snowflake introspection
- Optional LEARN schema support (Blackboard Open Database Schema, Premium tier)
- Read-only SQL policy with schema/table allowlists
- Metadata-grounded SQL planning without server-side LLM credentials
- Per-query confirmation by default with optional session-level approval
- Adaptive response payloads: summary text, table, Vega-Lite chart spec
- Budget tracking with configurable credit thresholds
- Async query execution for long-running jobs
- Planner feedback loop with optional persistence
- No-data diagnostics with auto-generated refinement candidates

## Supported domains

| Domain | Description | Refresh Rate |
|--------|-------------|-------------|
| **CDM_LMS** | Learning Management System (courses, grades, enrollments, assignments) | Overnight |
| **CDM_SIS** | Student Information System (students, terms, programs, registrations) | Daily |
| **CDM_TLM** | Teaching & Learning Metadata (telemetry, activity events, Ultra events) | Every 30 min |
| **CDM_ALY** | Analytics (daily metrics, KPI snapshots, dimensions) | Every 12 hours |
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

### LEARN schema (opt-in)
The LEARN schema provides access to 191+ raw Blackboard Learn source tables. It requires Illuminate Premium tier.

```bash
ENABLE_LEARN_SCHEMA=true
```

When enabled, `LEARN` is automatically added to `ALLOWED_DOMAINS` and `ALLOWED_SCHEMAS` — no need to add it manually.

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
| `REQUIRE_QUERY_CONFIRMATION` | `true` | Require `approved=true` per query |
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

### Planner probes (optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `PLANNER_PROBE_TIMEOUT_SECONDS` | `8` | Probe query timeout |
| `PLANNER_MAX_PROBES` | `2` | Max candidates to probe per request |

### Feedback persistence (optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `FEEDBACK_STORE_PATH` | `.planner_feedback.json` | File path for feedback data |

### Metadata introspection (optional)
| Variable | Default | Description |
|----------|---------|-------------|
| `METADATA_DICTIONARY_QUERY` | (empty) | Custom SQL returning TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DESCRIPTION |

## MCP tools

| Tool | Description |
|------|-------------|
| `list_domains` | List configured CDM domains |
| `list_entities` | List entities in a domain |
| `describe_entity` | Describe entity schema with column definitions |
| `plan_query` | Generate multiple ranked SQL candidates with confidence/complexity |
| `generate_sql` | Return recommended SQL (strict + fallback) from plan_query |
| `refine_sql` | Refine a failed query into strict and fallback retry candidates |
| `explain_query` | Validate SQL against read-only policy |
| `run_query` | Execute SQL synchronously with confirmation controls |
| `start_query` | Start async query execution, returns job ID |
| `get_query_status` | Poll async job status |
| `get_query_results` | Retrieve completed async job results |
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

## MCP prompts

| Prompt | Description |
|--------|-------------|
| `explore_lms_entities` | Guided exploration of LMS schema |
| `build_enrollment_trend_query` | Guided enrollment trend analysis (optional `term` parameter) |

## Output modes
- `auto` - Summary text + table; adds Vega-Lite chart when visualization intent is detected
- `text` - Summary text only
- `table` - Summary text + table data
- `viz` - Summary text + table + chart; returns `visualization_warning` if no suitable chart shape is found

Responses include `output_parts` so clients can render payload sections deterministically.

## Query planning workflow
1. Use `plan_query` to get multiple ranked SQL candidates
2. `generate_sql` returns the top recommended candidate
3. Execute with `run_query` (sync) or `start_query` (async)
4. If no data returned, check `no_data_diagnostics.refinement_candidates` in the response
5. Use `refine_sql` to get retry candidates for failed queries
6. Use `get_planner_feedback` to inspect execution history influencing rankings

## MCP compatibility
- Supports `prompts/list` and `prompts/get` for clients that resolve prompt payloads explicitly
- Tool execution failures are returned as `tools/call` results with `isError=true` (instead of terminating the JSON-RPC request), improving client interoperability
- Supports Content-Length framed stdio (default) and ndjson mode (`MCP_STDIO_MODE=ndjson`)

## Run tests
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Operations
See [OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) for startup checks, troubleshooting, and incident handling.

## Architecture
See [DESIGN.md](DESIGN.md) for design decisions and system architecture.

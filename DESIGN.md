# Illuminate MCP Server Design

## Objective
Build a local-first MCP server that allows chat clients to query Anthology Illuminate data in Snowflake across multiple CDM domains, using metadata-grounded SQL planning constrained by a strict read-only safety policy.

## Scope
- Transport: local `stdio` only (Content-Length framed, ndjson fallback)
- Data scope: 9 CDM domains (LMS, SIS, TLM, ALY, CLB, MAP, MEDIA, META) plus opt-in LEARN schema
- Querying: metadata-grounded SQL generation, refinable by the client LLM
- Runtime state: ephemeral (session-scoped), with optional feedback persistence
- Output: adaptive response with text summary, table data, and Vega-Lite visualization spec

## Supported Domains

| Domain | Source Product | Key Entities |
|--------|--------------|--------------|
| CDM_LMS | Blackboard Learn | Course, Enrollment, Grade, Assignment, Attempt, User, Content, Discussion |
| CDM_SIS | Anthology Student | Student, Academic Term, Program, Registration, Institution, Degree |
| CDM_TLM | Telemetry | Learner Activity, Learning Resource, Assessment Event, Ultra Events |
| CDM_ALY | Analytics | Metric Daily, Metric Dimension, KPI Snapshot |
| CDM_CLB | Collaborate | Session, Attendance, Recording |
| CDM_MAP | Mapping | User Map, Course Map |
| CDM_MEDIA | Video Studio | Media, Activity, Container, Person, Session Activity |
| CDM_META | Metadata | Data Source, Instance |
| LEARN | Blackboard Learn (Premium) | Users, Course Main, Course Users, Gradebook, Attempt, Forums, Announcements |

## Core Design Decisions
1. Query execution requires user confirmation by default.
2. Users can approve all queries for the current session via `set_session_approval`.
3. All Snowflake connectivity and limits are configured by the operator; no hardcoded institution details.
4. Domain routing auto-detects by question keywords, with user override and first-allowed-domain fallback.
5. Monthly credit budget is configurable with threshold warnings.
6. LEARN schema is opt-in via `ENABLE_LEARN_SCHEMA` — auto-injected into allowed domains/schemas when enabled.
7. SQL planning is metadata-driven (no server-side LLM API key required).
8. Builtin metadata catalog ships with all domains; Snowflake introspection overrides when enabled.

## High-Level Architecture

```
MCP Client (Claude Desktop, Inspector, etc.)
    |
    | stdio (Content-Length framed JSON-RPC 2.0)
    v
+--------------------------------------------------+
|  MCP Runtime Layer (mcp_server.py, stdio.py)     |
|  - JSON-RPC dispatch                              |
|  - Tools, Resources, Prompts                      |
+--------------------------------------------------+
    |
+--------------------------------------------------+
|  Tool Registry (tool_handlers.py)                 |
|  - 14 tools: metadata, planning, execution, gov   |
+--------------------------------------------------+
    |         |          |           |
    v         v          v           v
+--------+ +--------+ +----------+ +-----------+
| Config | | Meta   | | Planning | | Execution |
| Layer  | | Layer  | | Layer    | | Layer     |
+--------+ +--------+ +----------+ +-----------+
| config | | meta   | | planner  | | execution |
| .py    | | data   | | domain   | | snowflake |
|        | | .py    | | _router  | | _conn.py  |
|        | |        | | semantic | |           |
|        | |        | | _model   | |           |
+--------+ +--------+ +----------+ +-----------+
                          |
                    +----------+
                    | Refine   |
                    | Layer    |
                    +----------+
                    | refine   |
                    | ment.py  |
                    | tokens   |
                    | .py      |
                    +----------+
    |         |          |
    v         v          v
+--------+ +--------+ +-----------+
| Policy | | Output | | Govern-   |
| Layer  | | Layer  | | ance      |
+--------+ +--------+ +-----------+
| policy | | output | | budget.py |
| .py    | | .py    | | session   |
|        | |        | | feedback  |
|        | |        | | async_job |
+--------+ +--------+ +-----------+
```

## Tool Surface (14 tools)
- **Metadata:** `list_domains`, `list_entities`, `describe_entity`
- **Planning:** `plan_query`, `generate_sql`, `refine_sql`, `explain_query`
- **Execution:** `run_query`, `start_query`, `get_query_status`, `get_query_results`
- **Governance:** `get_planner_feedback`, `set_session_approval`, `get_budget_status`

## Resource Surface
- `illuminate://settings/runtime` - Non-secret runtime config
- `illuminate://metadata/catalog` - Full metadata snapshot
- `illuminate://metadata/status` - Introspection source and warnings
- `illuminate://metadata/entities/{domain}` - Domain entity listing
- `illuminate://metadata/entity/{domain}/{entity}` - Single entity detail

## Safety Model
- Allow only `SELECT` and CTE (`WITH ... SELECT`) query forms
- Block DDL, DML, multi-statement execution, and comments
- Enforce schema and table allowlists
- Per-query row limits and statement timeouts
- Per-query confirmation with session-level override
- Credit budget tracking with threshold warnings

## Module Overview

| Module | Responsibility |
|--------|---------------|
| `main.py` | CLI entrypoint |
| `mcp_server.py` | JSON-RPC dispatch, capabilities |
| `stdio.py` | Content-Length framed stdio transport |
| `config.py` | Environment-backed configuration with validation |
| `metadata.py` | Builtin catalog + Snowflake introspection |
| `domain_router.py` | Question-to-domain keyword routing |
| `semantic_model.py` | Entity/relationship graph for join inference |
| `planner.py` | Metadata-grounded SQL generation |
| `refinement.py` | Candidate scoring, refinement, probe profiling, diagnostics |
| `tokens.py` | Shared tokenization utilities |
| `policy.py` | Read-only SQL validation |
| `execution.py` | Snowflake query executor |
| `snowflake_conn.py` | Shared Snowflake connection factory |
| `output.py` | Adaptive output composition (text, table, Vega-Lite) |
| `tool_handlers.py` | Tool registry and handler dispatch |
| `session.py` | Ephemeral session state |
| `budget.py` | Credit budget tracking |
| `feedback.py` | Planner feedback with optional persistence |
| `async_jobs.py` | In-memory async job manager with TTL |
| `exceptions.py` | Exception hierarchy |

## Extensibility
- Domain definitions are data-driven — add new domains to the builtin catalog in `metadata.py`
- Domain routing keywords are configurable in `domain_router.py`
- Snowflake introspection discovers tables/columns dynamically when enabled
- Policy plugin points for future privacy and compliance controls

## Non-Goals (Current)
- HTTP deployment / auth flows
- Persistent query history
- Full privacy policy enforcement (PII masking deferred)
- Server-side LLM API calls

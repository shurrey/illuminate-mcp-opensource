# Workboard

## Sprint 1 — Foundation
- [x] Save design and implementation plan
- [x] Choose runtime stack (Python due local environment)
- [x] Stand up local `stdio` MCP runtime
- [x] Finalize config schema and validation
- [x] Register V1 tools/resources/prompts
- [x] Add SQL policy baseline and tests
- [x] Add Snowflake execution adapter skeleton
- [x] Add budget/approval session workflow
- [x] Validate with local smoke tests

## Sprint 2 — Query Pipeline
- [x] Real metadata introspection from Illuminate dictionary + Snowflake catalog (with builtin fallback)
- [x] LLM-backed SQL generation with grounded context
- [x] Query execution with result provenance and cost estimates
- [x] Adaptive output hardening (text/table/Vega-Lite)
- [x] Budget signals from Snowflake query history
- [x] Cross-client compatibility pass
- [x] Join- and intent-aware metadata planning for count/top/trend/list requests
- [x] Async query toolset (start_query/get_query_status/get_query_results)
- [x] Execution-feedback scoring for plan_query candidates
- [x] Optional persistent planner feedback storage
- [x] Strict-vs-fallback recommendation contract for generate_sql/plan_query
- [x] No-data diagnostics with executable refinement probes
- [x] refine_sql tool with feedback-aware ranking
- [x] auto_refine payload on no-data query results
- [x] Optional warehouse-rate credit estimation fallback
- [x] CDM_SIS builtin domain + routing tests

## Sprint 3 — MCP Apps & Interactive UI
- [x] Results Dashboard MCP App (results_app.py)
  - [x] Sortable/filterable table with lazy-loaded pagination (50 rows at a time)
  - [x] Chart.js visualization with auto-detected intent
  - [x] CSV export (full dataset regardless of pagination)
  - [x] Drill-down popover anchored to clicked cell with follow-up suggestions via sendMessage
  - [x] Cell popovers for JSON pretty-printing and long text
  - [x] ID columns rendered without locale formatting
- [x] Schema Explorer MCP App (schema_explorer_app.py)
  - [x] Domain sidebar with color-coded cards
  - [x] Entity grid with column counts and relationship counts
  - [x] Modal detail view with Schema + Data tabs
  - [x] On-demand column fetch via callServerTool (describe_entity)
  - [x] Data preview tab via callServerTool (run_query)
  - [x] Relationship navigation between entities
  - [x] Global search across domains, entities, cached columns
  - [x] "Analyze in chat" via sendMessage
  - [x] Description parser for structured metadata objects (descText)
- [x] Insights Feed MCP App (insights_app.py)
  - [x] 10 diagnostic queries across CDM_LMS, CDM_TLM, CDM_ALY, CDM_SIS
  - [x] Current term resolution from CDM_LMS.TERM
  - [x] Severity-ranked cards (critical/warning/info/ok) — all checks shown as health dashboard
  - [x] Info icon popover explaining what each check measures
  - [x] SQL icon popover showing exact query with copy button
  - [x] Severity and domain filters
  - [x] "Dig into this" drill-down via sendMessage
  - [x] Graceful handling of missing schemas (skipped vs failed)
  - [x] Queries run through executor (same pipeline as run_query)
- [x] SQL Viewer MCP App (sql_viewer_app.py)
  - [x] Syntax-highlighted SQL display
  - [x] Copy button
  - [x] "Run this query" and "Edit and run" via sendMessage

## Sprint 4 — Query Optimizer & Tool Separation
- [x] Query optimizer (query_optimizer.py)
  - [x] Automatic term scoping (~120 days for non-historical queries)
  - [x] Smart LIMIT inference based on question intent (25-5000)
  - [x] EXPLAIN pre-check for large scan warnings
  - [x] SELECT * hint and missing LIMIT detection
  - [x] Safety wrapper (never blocks execution on failure)
- [x] run_query / display_query separation
  - [x] run_query: no UI, default for all LLM data gathering
  - [x] display_query: renders Results Dashboard, only for final presentation
  - [x] display_sql: renders SQL Viewer, for query review
  - [x] Server instructions with numbered tool selection rules
- [x] Paginated results for large datasets
  - [x] display_query sends first 100 rows only
  - [x] get_result_page tool for app-initiated pagination
  - [x] IntersectionObserver triggers fetch on scroll
  - [x] 98% payload reduction (5KB vs 256KB for 5000 rows)
- [x] Payload optimization
  - [x] Removed vega_lite_spec data duplication (chart hints only)
  - [x] Slim content[0].text for display tools (summary, not full JSON)
- [x] REQUIRE_QUERY_CONFIRMATION default changed to false
- [x] .env auto-loading from project root
- [x] Empty domain filtering during metadata introspection
- [x] json.dumps default=str for datetime serialization safety
- [x] Corrected diagnostic SQL for actual CDM schema (PERSON_COURSE, COURSE_ACTIVITY, ACT_AS_INSTRUCTOR_IND, etc.)
- [x] NORMALIZED_SCORE threshold corrected (0-1 ratio, not 0-100)

## Backlog
- [ ] ID cross-referencing in previews (click COURSE_ID to view that COURSE record)
- [ ] Server-side column search across all entities
- [ ] Guided analysis workflows (term comparison, course health check, student risk)
- [ ] "How was this queried?" transparency panel in Results Dashboard
- [ ] Budget & governance dashboard MCP App
- [ ] KPI monitoring board MCP App

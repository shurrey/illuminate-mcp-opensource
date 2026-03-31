# Workboard

## Current Sprint
- [x] Save design and implementation plan
- [x] Choose runtime stack (Python due local environment)
- [x] Stand up local `stdio` MCP runtime
- [x] Finalize config schema and validation
- [x] Register V1 tools/resources/prompts
- [x] Add SQL policy baseline and tests
- [x] Add Snowflake execution adapter skeleton
- [x] Add budget/approval session workflow
- [x] Validate with local smoke tests

## Next Sprint
- [x] Real metadata introspection from Illuminate dictionary + Snowflake catalog (with builtin fallback)
- [x] LLM-backed SQL generation with grounded context
- [x] Query execution with result provenance and cost estimates (real Snowflake connectivity validated)
- [x] Adaptive output hardening (text/table/Vega-Lite)
- [x] Budget signals from Snowflake query history
- [x] Cross-client compatibility pass

- [x] Added join- and intent-aware metadata planning for count/top/trend/list requests
- [x] Added async query toolset (start_query/get_query_status/get_query_results) to avoid MCP request timeouts
- [x] Added execution-feedback scoring for plan_query candidates (confidence adjusts by success/runtimes)
- [x] Added optional persistent planner feedback storage across server restarts
- [x] Added strict-vs-fallback recommendation contract for generate_sql/plan_query
- [x] Added no-data diagnostics with executable refinement probes
- [x] Added refine_sql tool with feedback-aware ranking
- [x] Added auto_refine payload on no-data query results
- [x] Added optional warehouse-rate credit estimation fallback
- [x] Added CDM_SIS builtin domain + routing tests
- [x] Added release hardening docs and pinned Snowflake dependency path

# Illuminate MCP Server Implementation Plan

## Milestones

### M1. Foundation and Configuration
- Create repository scaffold for local MCP server
- Define strict config schema and defaults:
  - `MONTHLY_CREDIT_BUDGET=100`
  - confirmation required by default
  - `CDM_LMS` enabled by default
- Implement startup validation and clear failure messages

Exit criteria:
- Server starts in `stdio` mode with valid config
- Server exits with actionable errors on invalid/missing config

### M2. Metadata and Domain Routing
- Implement metadata loader for Illuminate dictionary + Snowflake schema metadata
- Build in-memory metadata cache with refresh controls
- Implement domain auto-detection with override and LMS fallback

Exit criteria:
- Domain and entity discovery works for `CDM_LMS`
- Routing is deterministic and overrideable

### M3. SQL Generation + Policy Engine
- Implement SQL generation from question + metadata context
- Add `explain_query` output with rationale
- Implement policy validation:
  - read-only enforcement
  - single statement enforcement
  - allowlist and limit checks

Exit criteria:
- Unsafe SQL is blocked
- Allowed SQL passes validation reliably

### M4. Confirmation Workflow + Query Execution
- Implement per-query approval as default behavior
- Implement session-level approval override (`approve-all`)
- Execute validated queries with tags and limits

Exit criteria:
- Confirmation behavior matches spec
- Session override resets when process exits

### M5. Adaptive Output + Visualization
- Build output composer for:
  - summary text
  - table structure
  - Vega-Lite spec when appropriate
- Add intent-based output mode selection and graceful fallbacks

Exit criteria:
- List/data/chart requests produce expected mixed-format responses

### M6. Budget Governance and Validation
- Add budget tracking interface and threshold warnings (70/85/100 default)
- Expose budget status tool
- Add end-to-end validation scenarios and security tests

Exit criteria:
- Budget warnings are emitted at thresholds
- Core user journeys pass validation

## Initial Work Breakdown
1. Save architecture docs and plan files.
2. Scaffold project structure and package configuration.
3. Implement config schema, defaults, and startup checks.
4. Implement MCP server skeleton and register planned tools/resources.
5. Add stubs for metadata, policy, execution, and output modules.
6. Add lightweight tests for config and policy baseline.

## Risks and Mitigations
- Risk: LLM-generated SQL can produce unsafe queries.
  - Mitigation: strict policy gate before execution; no bypass path.
- Risk: Cost unpredictability from open-ended querying.
  - Mitigation: hard technical limits + warnings + session confirmation defaults.
- Risk: Cross-client rendering variance for visualizations.
  - Mitigation: always include text/table fallback with Vega-Lite spec.

## Definition of Done for Current Sprint
- Documents saved in repo
- Project scaffold in place
- Local `stdio` MCP process starts
- Config validation implemented
- Tool interfaces wired with placeholder handlers

# Operator Runbook

## Purpose
Run, validate, and troubleshoot the local Illuminate MCP server for chat clients (Inspector, Claude Desktop, and other stdio MCP clients).

## Prerequisites
- `pyenv` installed and Python 3.12+ available
- Environment file configured at `.env` (copy from `.env.example`)
- Snowflake credentials populated when query execution or metadata introspection is enabled

## Setup

### 1. Set Python version
```bash
pyenv local 3.12.12
```

### 2. Install package
```bash
python -m pip install -e .
```

### 3. Install Snowflake connector
```bash
python -m pip install -r requirements-snowflake.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# Edit .env with your Snowflake credentials and settings
```

Key settings to configure:
- **Snowflake credentials** (`SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`)
- **Domains** (`ALLOWED_DOMAINS`) - Add domains you want to query. All 8 CDM domains are available: `CDM_LMS,CDM_SIS,CDM_TLM,CDM_ALY,CDM_CLB,CDM_MAP,CDM_MEDIA,CDM_META`
- **LEARN schema** - Set `ENABLE_LEARN_SCHEMA=true` if you have Illuminate Premium (auto-adds LEARN to domains)
- **Feature flags** - Enable `ENABLE_QUERY_EXECUTION=true` and `ENABLE_METADATA_INTROSPECTION=true` for live Snowflake connectivity

### 5. Verify installation
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Start Server

Generic:
```bash
illuminate-mcp
```

Inspector helper script:
```bash
./run_inspector_server.sh
```

## Health Checks

Run these in order after starting the server:

1. **Initialize** - MCP session handshake (automatic on client connect)
2. **`list_domains`** - Verify configured domains appear
3. **`list_entities`** for `CDM_LMS` - Verify entity listing (should include COURSE, GRADE, ENROLLMENT, etc.)
4. **`describe_entity`** for `COURSE` - Verify column definitions load
5. **`generate_sql`** with a simple prompt (e.g., "How many courses?") - Verify SQL planning works
6. **`run_query`** with `approved=true` on the generated SQL - Verify Snowflake execution works (requires `ENABLE_QUERY_EXECUTION=true`)
7. **`get_budget_status`** - Verify budget tracking is active

If LEARN is enabled, also:
8. **`list_entities`** for `LEARN` - Verify LEARN tables appear (USERS, COURSE_MAIN, etc.)

## Available Domains

| Domain | What it contains | When to use |
|--------|-----------------|-------------|
| CDM_LMS | Courses, grades, enrollments, assignments, content, discussions | Most common — LMS analytics |
| CDM_SIS | Students, terms, programs, registrations, degrees | Student records and academic data |
| CDM_TLM | Activity events, assessment events, Ultra events | Usage telemetry and engagement |
| CDM_ALY | Daily metrics, KPIs, dimensions | Institutional analytics dashboards |
| CDM_CLB | Collaborate sessions, attendance, recordings | Virtual classroom analytics |
| CDM_MAP | User and course identity mappings | Cross-domain joins |
| CDM_MEDIA | Video content, viewing activity | Video Studio analytics |
| CDM_META | Data sources, instance metadata | Reference data |
| LEARN | Raw Blackboard Learn tables (191+) | Direct source queries (Premium only) |

## Expected Runtime Behaviors
- Query execution requires confirmation by default unless session approval mode is `approve-all`
- Active rows are default (`ROW_DELETED_TIME IS NULL`) unless prompt explicitly requests deleted/all/historical rows
- `generate_sql` returns strict and fallback recommendations
- `run_query` returns adaptive output (`summary_text`, `table`, optional `vega_lite_spec`)
- `run_query` attaches `query_metrics` and `budget_signal_source` when available
- Completed async jobs are automatically cleaned up after 60 minutes

## Common Failures

### 1. MCP transport parse errors
**Symptom:** `Content-Length ... not valid JSON`
- Ensure framed stdio mode (default)
- Avoid printing non-MCP content to stdout
- Try `MCP_STDIO_MODE=ndjson` if client doesn't support Content-Length framing

### 2. Timeout errors
**Symptom:** `-32001` / Snowflake timeout
- Use async tools: `start_query`, `get_query_status`, `get_query_results`
- Increase `STATEMENT_TIMEOUT_SECONDS` if needed

### 3. No data from strict query
**Symptom:** Query returns 0 rows
- Review `no_data_diagnostics.refinement_candidates` in the response
- Use `auto_refine` payload or call `refine_sql`
- Check if term/course naming conventions match source data

### 4. Missing metadata
**Symptom:** Entities or columns missing from `describe_entity`
- Check `illuminate://metadata/status` resource
- If using introspection, verify Snowflake credentials and role permissions
- Disable introspection temporarily (`ENABLE_METADATA_INTROSPECTION=false`) to use builtin fallback

### 5. LEARN schema not appearing
**Symptom:** `list_entities` for LEARN returns empty
- Verify `ENABLE_LEARN_SCHEMA=true` in `.env`
- Verify Snowflake credentials have access to LEARN schema
- Builtin catalog has common LEARN tables; enable introspection for the full 191+ tables

### 6. Domain routing goes to wrong domain
**Symptom:** Query targets CDM_LMS when you meant CDM_SIS
- Use the `domain_override` parameter in `plan_query` or `generate_sql`
- Routing uses keyword matching — adding domain-specific terms helps (e.g., "GPA" routes to SIS)

## Incident Steps
1. Capture failing prompt/tool payload
2. Capture full server response (`structuredContent`)
3. Record current `.env` relevant values (without secrets)
4. Reproduce with `run_inspector_server.sh`
5. Run test suite before and after patching

## Rollback
- Revert to previous known-good code revision
- Keep `.env` unchanged
- Re-run health checks

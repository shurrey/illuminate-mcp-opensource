# Operator Runbook

## Purpose
Run, validate, and troubleshoot the local Illuminate MCP server for chat clients (Claude Desktop, ChatGPT, VS Code Copilot, and other MCP-compatible hosts).

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
- **Domains** (`ALLOWED_DOMAINS`) - Add domains you want to query
- **LEARN schema** - Set `ENABLE_LEARN_SCHEMA=true` if you have Illuminate Premium
- **Feature flags** - Enable `ENABLE_QUERY_EXECUTION=true` and `ENABLE_METADATA_INTROSPECTION=true` for live Snowflake connectivity

The server auto-loads `.env` from the project directory on startup. If the MCP client also passes env vars, those take precedence (`.env` only fills gaps).

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
3. **`list_entities`** for `CDM_LMS` - Verify entity listing
4. **`describe_entity`** for `COURSE` - Verify column definitions load
5. **`run_query`** with a simple SQL - Verify Snowflake execution works (requires `ENABLE_QUERY_EXECUTION=true`)
6. **`open_schema_explorer`** - Verify the Schema Explorer MCP App renders in the client
7. **`discover_insights`** - Verify the Insights Feed runs diagnostic queries and renders
8. **`get_budget_status`** - Verify budget tracking is active

## MCP Apps

The server renders interactive UI components inline in the conversation via MCP Apps:

| App | Triggered by | What to verify |
|-----|-------------|----------------|
| Results Dashboard | `display_query` | Table renders, sorting works, pagination loads more rows on scroll |
| Schema Explorer | `open_schema_explorer` | Domains show in sidebar, entity modal opens with columns, Data tab loads preview |
| Insights Feed | `discover_insights` | Findings cards appear, severity filters work, info/SQL popovers open |
| SQL Viewer | `display_sql` | SQL is syntax-highlighted, copy button works, "Run this query" sends to chat |

If MCP Apps don't render, verify your client supports the MCP Apps extension (Claude Desktop, ChatGPT, VS Code Copilot).

## Expected Runtime Behaviors
- Queries execute without server-side confirmation by default (MCP client provides its own approval UI)
- The query optimizer automatically adds term scoping and LIMIT to queries when appropriate
- Active rows are default (`ROW_DELETED_TIME IS NULL`) unless the prompt requests deleted/historical rows
- `run_query` returns data to the LLM with no UI; `display_query` renders the Results Dashboard
- The LLM should use `run_query` for analysis and `display_query` only for final presentation
- `display_query` sends only the first 100 rows; the dashboard fetches more as the user scrolls
- `discover_insights` resolves the current academic term from `CDM_LMS.TERM` and scopes LMS queries accordingly
- Domains with no tables in Snowflake are auto-excluded during metadata introspection

## Common Failures

### 1. MCP transport parse errors
**Symptom:** `Content-Length ... not valid JSON`
- Ensure framed stdio mode (default)
- Avoid printing non-MCP content to stdout
- Try `MCP_STDIO_MODE=ndjson` if client doesn't support Content-Length framing

### 2. display_query not rendering / stuck loading
**Symptom:** Dashboard doesn't appear or shows spinner indefinitely
- Check that your MCP client supports MCP Apps
- Verify the payload isn't too large — `display_query` should send max 100 rows initially
- Check `content[0].text` in the tool response — should be a brief summary, not a full JSON dump

### 3. Timeout errors
**Symptom:** `-32001` / Snowflake timeout
- Use async tools: `start_query`, `get_query_status`, `get_query_results`
- Increase `STATEMENT_TIMEOUT_SECONDS` if needed

### 4. discover_insights "execution disabled"
**Symptom:** Insights returns "requires query execution"
- Verify `ENABLE_QUERY_EXECUTION=true` in `.env`
- Verify the server was restarted after changing `.env`

### 5. Insight queries failing
**Symptom:** Queries show as "failed" or "skipped" in the Insights Feed
- "Skipped" = schema/table doesn't exist in your Snowflake share (expected for domains you don't have)
- "Failed" = real SQL error — click the `</>` icon on the card to see the exact SQL and error
- Common cause: column names differ from the builtin catalog when introspection is enabled

### 6. LLM using display_query for everything
**Symptom:** Every query renders a dashboard instead of the LLM analyzing data first
- The server instructions tell the LLM to use `run_query` as default — but some LLMs may ignore this
- Verify the server instructions mention "`run_query` is your DEFAULT query tool"
- Restart the server to ensure updated instructions are sent on initialization

### 7. No data from strict query
**Symptom:** Query returns 0 rows
- Check `no_data_diagnostics.refinement_candidates` in the response
- The query optimizer may have added term scoping — check `optimizations_applied` in the response
- Use `refine_sql` to get retry candidates

### 8. Missing metadata
**Symptom:** Entities or columns missing from `describe_entity`
- Check `illuminate://metadata/status` resource
- If using introspection, verify Snowflake credentials and role permissions
- Disable introspection temporarily to use builtin fallback

### 9. .env not loading
**Symptom:** Settings don't take effect after restart
- The server loads `.env` from the project directory (where `src/` is) and from `cwd`
- If the MCP client starts the server from a different directory, ensure `.env` is in the project root
- Env vars from the MCP client config take precedence over `.env`

## Incident Steps
1. Capture failing prompt/tool payload
2. Capture full server response (`structuredContent`)
3. Check `optimizations_applied` and `optimization_warnings` in query responses
4. For insights failures, check the "skipped" and "errors" lists in the response
5. Record current `.env` relevant values (without secrets)
6. Reproduce with `run_inspector_server.sh`
7. Run test suite before and after patching

## Rollback
- Revert to previous known-good code revision
- Keep `.env` unchanged
- Re-run health checks

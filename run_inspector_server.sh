#!/usr/bin/env bash
set -euo pipefail
cd /Users/scott.hurrey/local/illuminate-mcp

# Always use pyenv-managed Python for consistency with project runtime.
source ~/.zshrc >/dev/null 2>&1 || true
if command -v pyenv >/dev/null 2>&1; then
  eval "$(pyenv init -)"
fi

set -a
source .env
set +a
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src
export PYTHONWARNINGS=ignore
export MCP_STDIO_MODE=ndjson
exec python -u -m illuminate_mcp.main

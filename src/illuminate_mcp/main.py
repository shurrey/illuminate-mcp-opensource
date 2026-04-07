"""CLI entrypoint."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .config import AppConfig
from .exceptions import ConfigError
from .mcp_server import MCPServer
from .stdio import serve


def _load_dotenv() -> None:
    """Load .env file into os.environ if present. No dependencies required."""
    # Look in cwd first, then project root (two levels up from this file)
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    env_path = next((p for p in candidates if p.is_file()), None)
    if env_path is None:
        return
    with open(env_path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            # Don't override values already set in the real environment
            if key not in os.environ:
                os.environ[key] = value


def main() -> int:
    _load_dotenv()
    try:
        config = AppConfig.from_env(os.environ)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    server = MCPServer(config)
    serve(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

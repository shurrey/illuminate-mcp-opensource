"""CLI entrypoint."""

from __future__ import annotations

import os
import sys

from .config import AppConfig
from .exceptions import ConfigError
from .mcp_server import MCPServer
from .stdio import serve


def main() -> int:
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

"""Content-Length framed stdio transport for MCP."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional

from .mcp_server import MCPServer


def _read_message() -> Optional[Dict[str, Any]]:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break

        decoded = line.decode("utf-8").strip()
        if not decoded:
            continue

        # Compatibility fallback for clients that send newline-delimited JSON.
        if decoded.startswith("{"):
            return json.loads(decoded)

        if ":" not in decoded:
            continue
        key, value = decoded.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        return None

    body = sys.stdin.buffer.read(content_length)
    if not body:
        return None

    return json.loads(body.decode("utf-8"))


def _write_message(message: Dict[str, Any]) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    mode = os.environ.get("MCP_STDIO_MODE", "framed").strip().lower()
    if mode == "ndjson":
        sys.stdout.buffer.write(payload + b"\n")
        sys.stdout.buffer.flush()
        return

    header = f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8")
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def serve(server: MCPServer) -> None:
    while True:
        request = _read_message()
        if request is None:
            break

        response = server.handle(request)
        if response is not None:
            _write_message(response)

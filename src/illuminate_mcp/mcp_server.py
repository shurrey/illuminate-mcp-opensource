"""Minimal MCP JSON-RPC request dispatcher."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from .budget import BudgetTracker
from .config import AppConfig
from .domain_router import DomainRouter
from .exceptions import IlluminateMCPError
from .execution import SnowflakeExecutor
from .metadata import MetadataLoadStatus, MetadataStore, build_metadata_store
from .output import OutputComposer
from .planner import SqlPlanner
from .policy import SqlPolicy
from .insights_app import (
    INSIGHTS_FEED_CSP,
    INSIGHTS_FEED_URI,
    insights_feed_html,
)
from .results_app import (
    RESULTS_DASHBOARD_CSP,
    RESULTS_DASHBOARD_URI,
    results_dashboard_html,
)
from .schema_explorer_app import (
    SCHEMA_EXPLORER_CSP,
    SCHEMA_EXPLORER_URI,
    schema_explorer_html,
)
from .session import SessionState
from .sql_viewer_app import (
    SQL_VIEWER_CSP,
    SQL_VIEWER_URI,
    sql_viewer_html,
)
from .tool_handlers import ToolRegistry


class MCPServer:
    def __init__(self, config: AppConfig):
        self._config = config
        self._metadata = MetadataStore.from_builtin_catalog(config.allowed_domains)
        self._metadata_status = MetadataLoadStatus(
            source="deferred" if config.enable_metadata_introspection else "builtin",
            warning=None,
        )
        self._metadata_loaded = False

        router = DomainRouter(config.allowed_domains)
        policy = SqlPolicy(config.allowed_schemas, config.allowed_tables)
        session = SessionState(
            require_query_confirmation=config.require_query_confirmation,
            approval_mode=config.default_session_approval_mode,
        )
        budget = BudgetTracker(config.monthly_credit_budget, config.budget_warning_thresholds)
        executor = SnowflakeExecutor(config)
        output = OutputComposer(config.max_text_summary_length)
        planner = SqlPlanner(config, router)

        self._tools = ToolRegistry(
            config=config,
            metadata=self._metadata,
            router=router,
            policy=policy,
            session=session,
            budget=budget,
            executor=executor,
            output=output,
            planner=planner,
        )

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if not method:
            return self._error(request_id, -32600, "Invalid Request: missing method")

        try:
            if method == "initialize":
                return self._result(request_id, self._initialize())
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                return self._result(request_id, {"tools": self._tools.tool_definitions()})
            if method == "tools/call":
                payload = self._call_tool(params)
                return self._result(request_id, payload)
            if method == "resources/list":
                return self._result(request_id, self._list_resources())
            if method == "resources/read":
                return self._result(request_id, self._read_resource(params))
            if method == "resources/templates/list":
                return self._result(request_id, self._list_resource_templates())
            if method == "prompts/list":
                return self._result(request_id, self._list_prompts())
            if method == "prompts/get":
                return self._result(request_id, self._get_prompt(params))
            if method == "notifications/initialized":
                return None

            return self._error(request_id, -32601, f"Method not found: {method}")
        except IlluminateMCPError as exc:
            return self._error(request_id, -32001, str(exc))
        except Exception as exc:  # pragma: no cover
            return self._error(request_id, -32000, f"Unhandled server error: {exc}")

    @staticmethod
    def _result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any] | None:
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    @staticmethod
    def _error(request_id: Any, code: int, message: str) -> Dict[str, Any] | None:
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def _initialize(self) -> Dict[str, Any]:
        metadata_note = f"metadata source={self._metadata_status.source}"
        if self._metadata_status.warning:
            metadata_note = f"{metadata_note}; warning={self._metadata_status.warning}"

        return {
            "protocolVersion": "2025-06-18",
            "serverInfo": {
                "name": "illuminate-mcp",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False},
                "prompts": {"listChanged": False},
            },
            "instructions": (
                "IMPORTANT — Tool selection rules:\n"
                "1. run_query is your DEFAULT query tool. Use it for ALL data gathering and analysis. "
                "It returns results to you with no UI rendered.\n"
                "2. display_query is ONLY for showing the user an interactive dashboard. Call it AFTER "
                "you have already gathered data with run_query and are ready to present final results. "
                "Pass the same SQL you used with run_query (Snowflake caches results). "
                "If the answer is text analysis, do NOT call display_query.\n"
                "3. display_sql is for when the user asks to see or review a SQL query.\n"
                "4. discover_insights is for when the user asks for anomalies, red flags, or what to look at.\n"
                "5. open_schema_explorer is ONLY when the user explicitly asks to browse the schema.\n"
                "6. list_domains/list_entities/describe_entity are for query planning.\n"
                + metadata_note
            ),
        }

    def _call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str):
            raise ValueError("tools/call requires params.name")

        if name in {"open_schema_explorer", "list_domains", "list_entities", "describe_entity", "generate_sql", "plan_query"}:
            self._ensure_metadata_loaded()

        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("tools/call params.arguments must be an object")

        try:
            payload = self._tools.call(name, arguments)
        except IlluminateMCPError as exc:
            error_payload = {
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "tool": name,
            }
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(error_payload, indent=2, sort_keys=True, default=str),
                    }
                ],
                "structuredContent": error_payload,
                "isError": True,
            }

        # For display tools with UI, send a slim text summary to the LLM
        # (the full data goes to the app via structuredContent)
        if name in {"display_query", "display_sql", "discover_insights", "open_schema_explorer"}:
            summary = payload.get("output", {}).get("summary_text") or payload.get("status", "ok")
            text_content = summary
        else:
            text_content = json.dumps(payload, indent=2, sort_keys=True, default=str)

        return {
            "content": [
                {
                    "type": "text",
                    "text": text_content,
                }
            ],
            "structuredContent": payload,
            "isError": False,
        }

    @staticmethod
    def _list_resources() -> Dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": "illuminate://settings/runtime",
                    "name": "Runtime Settings",
                    "description": "Current non-secret runtime configuration",
                    "mimeType": "application/json",
                },
                {
                    "uri": "illuminate://metadata/catalog",
                    "name": "Metadata Catalog",
                    "description": "Domain and entity metadata snapshot",
                    "mimeType": "application/json",
                },
                {
                    "uri": "illuminate://metadata/status",
                    "name": "Metadata Status",
                    "description": "Metadata source and fallback warning details",
                    "mimeType": "application/json",
                },
                {
                    "uri": "illuminate://metadata/entities/{domain}",
                    "name": "Domain Entities Template",
                    "description": "Template URI for domain-level entity listings",
                    "mimeType": "application/json",
                },
                {
                    "uri": "illuminate://metadata/entity/{domain}/{entity}",
                    "name": "Entity Details Template",
                    "description": "Template URI for a single entity description",
                    "mimeType": "application/json",
                },
                {
                    "uri": RESULTS_DASHBOARD_URI,
                    "name": "Results Dashboard",
                    "description": "Interactive query results dashboard (MCP App)",
                    "mimeType": "text/html;profile=mcp-app",
                    "_meta": {
                        "ui": {
                            "csp": RESULTS_DASHBOARD_CSP,
                            "prefersBorder": True,
                        },
                    },
                },
                {
                    "uri": SCHEMA_EXPLORER_URI,
                    "name": "Schema Explorer",
                    "description": "Interactive schema browser with entity relationships (MCP App)",
                    "mimeType": "text/html;profile=mcp-app",
                    "_meta": {
                        "ui": {
                            "csp": SCHEMA_EXPLORER_CSP,
                            "prefersBorder": True,
                        },
                    },
                },
                {
                    "uri": SQL_VIEWER_URI,
                    "name": "SQL Viewer",
                    "description": "Syntax-highlighted SQL viewer with copy and run buttons (MCP App)",
                    "mimeType": "text/html;profile=mcp-app",
                    "_meta": {
                        "ui": {
                            "csp": SQL_VIEWER_CSP,
                            "prefersBorder": True,
                        },
                    },
                },
                {
                    "uri": INSIGHTS_FEED_URI,
                    "name": "Insights Feed",
                    "description": "Interactive anomaly and trend findings feed (MCP App)",
                    "mimeType": "text/html;profile=mcp-app",
                    "_meta": {
                        "ui": {
                            "csp": INSIGHTS_FEED_CSP,
                            "prefersBorder": True,
                        },
                    },
                },
            ]
        }

    @staticmethod
    def _list_resource_templates() -> Dict[str, Any]:
        return {
            "resourceTemplates": [
                {
                    "uriTemplate": "illuminate://metadata/entities/{domain}",
                    "name": "Entities by Domain",
                    "description": "List entity metadata for the provided domain",
                    "mimeType": "application/json",
                },
                {
                    "uriTemplate": "illuminate://metadata/entity/{domain}/{entity}",
                    "name": "Entity by Name",
                    "description": "Return metadata for one entity in a domain",
                    "mimeType": "application/json",
                },
            ]
        }

    def _read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params.get("uri")
        if uri == "illuminate://settings/runtime":
            contents = self._config.public_settings()
        elif uri == "illuminate://metadata/catalog":
            self._ensure_metadata_loaded()
            contents = self._metadata.resource_snapshot()
        elif uri == "illuminate://metadata/status":
            contents = {
                "source": self._metadata_status.source,
                "warning": self._metadata_status.warning,
            }
        elif isinstance(uri, str) and uri.startswith("illuminate://metadata/entities/"):
            self._ensure_metadata_loaded()
            domain = uri.split("/")[-1].upper()
            contents = {
                "domain": domain,
                "entities": self._metadata.list_entities(domain),
            }
        elif isinstance(uri, str) and uri.startswith("illuminate://metadata/entity/"):
            self._ensure_metadata_loaded()
            match = re.match(r"^illuminate://metadata/entity/([^/]+)/([^/]+)$", uri)
            if not match:
                raise ValueError(f"Invalid entity resource URI: {uri}")
            domain = match.group(1).upper()
            entity = match.group(2).upper()
            described = self._metadata.describe_entity(domain, entity)
            if not described:
                raise ValueError(f"Unknown entity URI: {uri}")
            contents = described
        elif uri == RESULTS_DASHBOARD_URI:
            return {
                "contents": [
                    {
                        "uri": RESULTS_DASHBOARD_URI,
                        "mimeType": "text/html;profile=mcp-app",
                        "text": results_dashboard_html(),
                    }
                ]
            }
        elif uri == SCHEMA_EXPLORER_URI:
            return {
                "contents": [
                    {
                        "uri": SCHEMA_EXPLORER_URI,
                        "mimeType": "text/html;profile=mcp-app",
                        "text": schema_explorer_html(),
                    }
                ]
            }
        elif uri == SQL_VIEWER_URI:
            return {
                "contents": [
                    {
                        "uri": SQL_VIEWER_URI,
                        "mimeType": "text/html;profile=mcp-app",
                        "text": sql_viewer_html(),
                    }
                ]
            }
        elif uri == INSIGHTS_FEED_URI:
            return {
                "contents": [
                    {
                        "uri": INSIGHTS_FEED_URI,
                        "mimeType": "text/html;profile=mcp-app",
                        "text": insights_feed_html(),
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown resource URI: {uri}")

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(contents, indent=2, sort_keys=True),
                }
            ]
        }

    @staticmethod
    def _list_prompts() -> Dict[str, Any]:
        return {
            "prompts": [
                {
                    "name": "explore_lms_entities",
                    "description": "Inspect available LMS entities and column definitions",
                    "arguments": [],
                },
                {
                    "name": "build_enrollment_trend_query",
                    "description": "Draft query for enrollment trend analysis",
                    "arguments": [
                        {
                            "name": "term",
                            "required": False,
                        }
                    ],
                },
            ]
        }

    @staticmethod
    def _get_prompt(params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("prompts/get requires params.name")

        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            raise ValueError("prompts/get params.arguments must be an object")

        normalized = name.strip()
        if normalized == "explore_lms_entities":
            text = (
                "Use list_domains, then list_entities for CDM_LMS, then describe_entity "
                "for relevant tables before writing SQL."
            )
        elif normalized == "build_enrollment_trend_query":
            term = str(args.get("term", "")).strip()
            scope = f" for term {term}" if term else ""
            text = (
                "Draft a read-only SQL query that shows enrollment trend over time"
                f"{scope}. Include PERIOD and RECORD_COUNT."
            )
        else:
            raise ValueError(f"Unknown prompt name: {normalized}")

        return {
            "description": f"Prompt payload for {normalized}",
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": text},
                }
            ],
        }

    def _ensure_metadata_loaded(self) -> None:
        if self._metadata_loaded:
            return
        self._metadata_loaded = True

        if not self._config.enable_metadata_introspection:
            self._metadata_status = MetadataLoadStatus(source="builtin", warning=None)
            return

        metadata, status = build_metadata_store(self._config)
        self._metadata = metadata
        self._metadata_status = status
        self._tools.set_metadata(metadata)

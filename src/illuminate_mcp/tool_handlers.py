"""Tool registry and handler implementations."""

from __future__ import annotations

from typing import Any, Dict, List
import re
import time
import uuid

from .async_jobs import AsyncJobManager
from .budget import BudgetTracker
from .config import AppConfig
from .domain_router import DomainRouter
from .exceptions import ToolError
from .execution import SnowflakeExecutor
from .feedback import PlannerFeedbackStore
from .metadata import MetadataStore
from .output import OutputComposer
from .planner import SqlPlanner
from .policy import SqlPolicy
from .query_optimizer import optimize_query
from .refinement import CandidateEngine, extract_entities_from_sql, probe_rank
from .insights import run_diagnostics
from .insights_app import INSIGHTS_FEED_URI
from .results_app import RESULTS_DASHBOARD_URI
from .schema_explorer_app import SCHEMA_EXPLORER_URI
from .semantic_model import SemanticModel
from .sql_viewer_app import SQL_VIEWER_URI
from .session import SessionState


class ToolRegistry:
    def __init__(
        self,
        config: AppConfig,
        metadata: MetadataStore,
        router: DomainRouter,
        policy: SqlPolicy,
        session: SessionState,
        budget: BudgetTracker,
        executor: SnowflakeExecutor,
        output: OutputComposer,
        planner: SqlPlanner,
    ):
        self._config = config
        self._metadata = metadata
        self._router = router
        self._policy = policy
        self._session = session
        self._budget = budget
        self._executor = executor
        self._output = output
        self._planner = planner
        self._jobs = AsyncJobManager()
        self._result_cache: Dict[str, dict] = {}  # result_id -> {columns, rows, sql, question}
        persist_path = config.feedback_store_path if config.enable_persistent_feedback else None
        self._feedback = PlannerFeedbackStore(persist_path=persist_path)
        self._engine = CandidateEngine(
            config=config,
            executor=executor,
            feedback=self._feedback,
            policy=policy,
        )

        self._tools = {
            "open_schema_explorer": self._open_schema_explorer,
            "list_domains": self._list_domains,
            "list_entities": self._list_entities,
            "describe_entity": self._describe_entity,
            "plan_query": self._plan_query,
            "generate_sql": self._generate_sql,
            "refine_sql": self._refine_sql,
            "explain_query": self._explain_query,
            "run_query": self._run_query,
            "display_query": self._display_query,
            "display_sql": self._display_sql,
            "start_query": self._start_query,
            "get_query_status": self._get_query_status,
            "get_query_results": self._get_query_results,
            "discover_insights": self._discover_insights,
            "get_planner_feedback": self._get_planner_feedback,
            "set_session_approval": self._set_session_approval,
            "get_budget_status": self._get_budget_status,
        }

    def set_metadata(self, metadata: MetadataStore) -> None:
        """Update the metadata store after deferred loading."""
        self._metadata = metadata

    def tool_definitions(self) -> List[dict]:
        return [
            {
                "name": "open_schema_explorer",
                "description": (
                    "Open the interactive visual schema explorer for the user to browse domains, "
                    "entities, columns, and relationships. Only call this when the user explicitly "
                    "asks to explore or browse the schema. Do NOT call this for query planning — "
                    "use list_domains, list_entities, and describe_entity instead."
                ),
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                "_meta": {
                    "ui": {"resourceUri": SCHEMA_EXPLORER_URI},
                },
            },
            {
                "name": "list_domains",
                "description": "List configured CDM domains",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "list_entities",
                "description": "List entities for a domain",
                "inputSchema": {
                    "type": "object",
                    "properties": {"domain": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            {
                "name": "describe_entity",
                "description": "Describe a domain entity and columns",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "entity": {"type": "string"},
                    },
                    "required": ["entity"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "plan_query",
                "description": "Produce multiple SQL candidates with confidence and complexity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "domain_override": {"type": "string"},
                        "output_intent": {"type": "string"},
                    },
                    "required": ["question"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "generate_sql",
                "description": "Generate a starter SQL query from a question and metadata",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "domain_override": {"type": "string"},
                        "output_intent": {"type": "string"},
                    },
                    "required": ["question"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "refine_sql",
                "description": "Refine a failed SQL query into strict and fallback retry candidates",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "failed_sql": {"type": "string"},
                    },
                    "required": ["question", "failed_sql"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "explain_query",
                "description": "Validate and explain query policy fit",
                "inputSchema": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "run_query",
                "description": (
                    "Execute SQL and return results. Use this for intermediate data gathering "
                    "during analysis. No interactive UI is rendered. For presenting final results "
                    "to the user with an interactive dashboard, use display_query instead."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                        "question": {"type": "string"},
                        "row_limit": {"type": "integer"},
                        "output_mode": {"type": "string"},
                        "approved": {"type": "boolean"},
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "display_query",
                "description": (
                    "Display results in an interactive dashboard for the user. "
                    "Preferred: pass result_id from a previous run_query response (avoids re-serializing data). "
                    "Alternative: pass columns and rows directly for small datasets. "
                    "Only call this when presenting final results the user should see."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "result_id": {
                            "type": "string",
                            "description": "result_id from a previous run_query response (preferred — avoids large payloads)",
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column names (alternative to result_id, for small datasets)",
                        },
                        "rows": {
                            "type": "array",
                            "items": {"type": "array"},
                            "description": "Row data (alternative to result_id, for small datasets)",
                        },
                        "question": {"type": "string"},
                        "sql": {"type": "string", "description": "The SQL that produced these results (for reference)"},
                    },
                    "additionalProperties": False,
                },
                "_meta": {
                    "ui": {"resourceUri": RESULTS_DASHBOARD_URI},
                },
            },
            {
                "name": "display_sql",
                "description": (
                    "Display a SQL query in an interactive viewer with syntax highlighting and copy button. "
                    "Use this when the user asks to see, generate, or review a SQL query. "
                    "Do NOT use this for running queries — use run_query or display_query instead."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "The SQL query to display"},
                        "title": {"type": "string", "description": "Title for the query (e.g., 'Enrollment by Term')"},
                        "description": {"type": "string", "description": "Explanation of what the query does"},
                        "domain": {"type": "string", "description": "The CDM domain this query targets"},
                        "confidence": {"type": "number", "description": "Confidence score (0-1) if from the planner"},
                        "complexity": {"type": "string", "description": "Complexity level (low/moderate/high)"},
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
                "_meta": {
                    "ui": {"resourceUri": SQL_VIEWER_URI},
                },
            },
            {
                "name": "start_query",
                "description": "Start async query execution and return a job id",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string"},
                        "question": {"type": "string"},
                        "row_limit": {"type": "integer"},
                        "output_mode": {"type": "string"},
                        "approved": {"type": "boolean"},
                    },
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_query_status",
                "description": "Poll status for an async query job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                    "required": ["job_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_query_results",
                "description": "Retrieve results for a completed async query job",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                    "required": ["job_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_planner_feedback",
                "description": "Show in-memory planner feedback statistics from executed queries",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "set_session_approval",
                "description": "Set approval behavior for this process session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["per-query", "approve-all"],
                        }
                    },
                    "required": ["mode"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_budget_status",
                "description": "Return current budget tracking status",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "discover_insights",
                "description": (
                    "Scan configured domains for data anomalies, trends, and potential issues. "
                    "Returns ranked insight cards with severity levels. Call this when the user "
                    "asks for insights, red flags, anomalies, or what they should be looking at. "
                    "Requires query execution to be enabled."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional subset of domains to scan. Defaults to all configured domains.",
                        },
                    },
                    "additionalProperties": False,
                },
                "_meta": {
                    "ui": {"resourceUri": INSIGHTS_FEED_URI},
                },
            },
        ]

    def call(self, name: str, arguments: Dict[str, Any]) -> dict:
        handler = self._tools.get(name)
        if not handler:
            raise ToolError(f"Unknown tool: {name}")
        return handler(arguments)

    # ------------------------------------------------------------------
    # Schema explorer
    # ------------------------------------------------------------------

    def _open_schema_explorer(self, _arguments: Dict[str, Any]) -> dict:
        # Lightweight catalog: domain/entity names and descriptions only.
        # Column details are fetched on demand via describe_entity.
        catalog: Dict[str, dict] = {}
        for domain_info in self._metadata.list_domains():
            domain_name = domain_info["name"]
            entities: Dict[str, dict] = {}
            for entity_info in self._metadata.list_entities(domain_name):
                entities[entity_info["name"]] = {
                    "description": entity_info.get("description", ""),
                    "column_count": entity_info.get("column_count", 0),
                }
            catalog[domain_name] = {
                "description": domain_info.get("description", ""),
                "entities": entities,
            }

        rels: Dict[str, list] = {}
        for domain in self._metadata.domains():
            model = SemanticModel.from_metadata(self._metadata, domain)
            seen: set = set()
            domain_rels = []
            for rel in model.relationships:
                key = tuple(sorted([(rel.source_entity, rel.source_column),
                                     (rel.target_entity, rel.target_column)]))
                if key in seen:
                    continue
                seen.add(key)
                domain_rels.append({
                    "source_entity": rel.source_entity,
                    "source_column": rel.source_column,
                    "target_entity": rel.target_entity,
                    "target_column": rel.target_column,
                    "confidence": round(rel.confidence, 2),
                })
            rels[domain] = domain_rels
        return {"catalog": catalog, "relationships": rels}

    # ------------------------------------------------------------------
    # Metadata tools
    # ------------------------------------------------------------------

    def _list_domains(self, _arguments: Dict[str, Any]) -> dict:
        return {"domains": self._metadata.list_domains()}

    def _list_entities(self, arguments: Dict[str, Any]) -> dict:
        domain = arguments.get("domain") or self._config.allowed_domains[0]
        return {"domain": domain, "entities": self._metadata.list_entities(domain)}

    def _describe_entity(self, arguments: Dict[str, Any]) -> dict:
        entity = (arguments.get("entity") or "").strip().upper()
        if not entity:
            raise ToolError("entity is required")

        domain = arguments.get("domain")
        if not domain:
            for configured_domain in self._metadata.domains():
                description = self._metadata.describe_entity(configured_domain, entity)
                if description:
                    return description
            raise ToolError(f"entity {entity!r} not found")

        description = self._metadata.describe_entity(domain, entity)
        if not description:
            raise ToolError(f"entity {entity!r} not found in domain {domain!r}")
        return description

    # ------------------------------------------------------------------
    # SQL generation tools
    # ------------------------------------------------------------------

    def _generate_sql(self, arguments: Dict[str, Any]) -> dict:
        planned = self._plan_query(arguments)
        candidates = planned.get("candidates", [])
        if not candidates:
            raise ToolError("No SQL candidates could be generated")
        strict_index = int(planned.get("recommended_strict_index", 0))
        fallback_index = int(planned.get("recommended_fallback_index", strict_index))
        recommended = candidates[strict_index]
        fallback = candidates[fallback_index]
        alternatives = [
            c
            for i, c in enumerate(candidates)
            if i not in {strict_index, fallback_index}
        ][:2]
        return {
            "domain": planned["domain"],
            "sql": recommended["sql"],
            "planner_mode": recommended["planner_mode"],
            "rationale": recommended["rationale"],
            "grounded_entities": recommended["grounded_entities"],
            "warning": recommended["warning"],
            "confidence": recommended["confidence"],
            "complexity": recommended["complexity"],
            "probe": recommended.get("probe"),
            "candidate_count": len(candidates),
            "recommended_strict": recommended,
            "recommended_fallback": fallback,
            "alternatives": alternatives,
        }

    def _plan_query(self, arguments: Dict[str, Any]) -> dict:
        question = (arguments.get("question") or "").strip()
        if not question:
            raise ToolError("question is required")

        engine = self._engine
        intents = engine.candidate_intents(question, arguments.get("output_intent"))
        candidates = []
        seen_sql: set = set()
        domain: str | None = None
        for intent in intents:
            plan = self._planner.plan(
                question=question,
                metadata=self._metadata,
                domain_override=arguments.get("domain_override"),
                output_intent=intent,
            )
            if domain is None:
                domain = plan.domain
            normalized_sql = plan.sql.strip()
            if normalized_sql in seen_sql:
                continue
            seen_sql.add(normalized_sql)
            confidence = engine.estimate_confidence(plan.warning, plan.planner_mode, normalized_sql)
            complexity = engine.estimate_complexity(normalized_sql)
            signature = engine.sql_signature(
                normalized_sql,
                list(plan.grounded_entities),
                complexity,
            )
            feedback = self._feedback.get(signature)
            confidence = engine.apply_feedback_adjustment(confidence, feedback.success_rate, feedback.avg_seconds)
            confidence = engine.apply_intent_alignment(confidence, question, normalized_sql)
            candidates.append(
                {
                    "sql": normalized_sql,
                    "planner_mode": plan.planner_mode,
                    "rationale": plan.rationale,
                    "grounded_entities": list(plan.grounded_entities),
                    "warning": plan.warning,
                    "confidence": confidence,
                    "complexity": complexity,
                    "feedback": {
                        "attempts": feedback.attempts,
                        "success_rate": round(feedback.success_rate, 3),
                        "avg_seconds": round(feedback.avg_seconds, 4),
                    },
                }
            )

        if not candidates:
            raise ToolError("No SQL candidates could be generated")

        candidates = engine.add_relaxed_analysis_candidates(candidates)
        candidates = engine.apply_requirement_alignment(question, candidates)
        engine.profile_candidates(question, candidates)
        candidates = engine.apply_robustness_adjustments(question, candidates)

        ranked_all = sorted(
            candidates,
            key=lambda item: (
                -probe_rank(item),
                -item["confidence"],
                {"low": 0, "moderate": 1, "high": 2}[item["complexity"]],
            ),
        )
        strict_candidates = [c for c in ranked_all if not engine.is_relaxed_candidate(c)]
        fallback_candidates = [c for c in ranked_all if engine.is_relaxed_candidate(c)]
        ranked_candidates = strict_candidates + fallback_candidates
        strict_index = 0
        fallback_index = (
            len(strict_candidates)
            if fallback_candidates
            else strict_index
        )
        strict_best = ranked_candidates[strict_index]
        fallback_best = ranked_candidates[fallback_index]

        return {
            "domain": domain,
            "recommended_strict_index": strict_index,
            "recommended_fallback_index": fallback_index,
            "recommended_strict_reason": (
                f"Selected best semantic-match candidate "
                f"(confidence={strict_best['confidence']}, complexity={strict_best['complexity']})."
            ),
            "recommended_fallback_reason": (
                f"Selected best fallback candidate for likely data return "
                f"(confidence={fallback_best['confidence']}, complexity={fallback_best['complexity']})."
            ),
            "candidates": ranked_candidates,
        }

    def _refine_sql(self, arguments: Dict[str, Any]) -> dict:
        question = (arguments.get("question") or "").strip()
        failed_sql = (arguments.get("failed_sql") or "").strip()
        if not question:
            raise ToolError("question is required")
        if not failed_sql:
            raise ToolError("failed_sql is required")

        engine = self._engine
        validated = self._policy.validate(failed_sql)
        normalized_sql = validated.normalized_sql
        refinements = engine.build_sql_refinement_candidates(normalized_sql, question)
        if not refinements:
            refinements = [
                {
                    "label": "retry_baseline",
                    "strictness": "strict",
                    "rationale": "No deterministic refinement detected; retry baseline SQL.",
                    "sql": normalized_sql,
                    "confidence": 0.5,
                }
            ]

        refinements = engine.apply_refinement_feedback(question, refinements)
        engine.profile_refinement_candidates(question, refinements)
        refinements = sorted(
            refinements,
            key=lambda item: (
                0 if item.get("strictness") == "strict" else 1,
                -probe_rank(item),
                -float(item.get("confidence", 0.0)),
            ),
        )

        strict = [item for item in refinements if item.get("strictness") == "strict"]
        fallback = [item for item in refinements if item.get("strictness") == "fallback"]
        strict_best = strict[0] if strict else refinements[0]
        fallback_best = fallback[0] if fallback else strict_best

        return {
            "strict_refined": strict_best,
            "fallback_refined": fallback_best,
            "candidate_count": len(refinements),
            "candidates": refinements,
            "notes": [
                "strict_refined preserves requested constraints where possible.",
                "fallback_refined prioritizes data return for iterative debugging.",
            ],
        }

    def _explain_query(self, arguments: Dict[str, Any]) -> dict:
        sql = arguments.get("sql")
        if not isinstance(sql, str):
            raise ToolError("sql is required")

        result = self._policy.validate(sql)
        return {
            "normalized_sql": result.normalized_sql,
            "referenced_objects": list(result.referenced_objects),
            "policy_status": "allowed",
        }

    # ------------------------------------------------------------------
    # Query execution tools
    # ------------------------------------------------------------------

    def _run_query(self, arguments: Dict[str, Any]) -> dict:
        sql = arguments.get("sql")
        if not isinstance(sql, str):
            raise ToolError("sql is required")

        prepared = self._prepare_query(arguments, sql)
        if "needs_confirmation" in prepared:
            return prepared["needs_confirmation"]

        result = self._execute_query(
            normalized_sql=prepared["normalized_sql"],
            referenced_objects=prepared["referenced_objects"],
            row_limit=prepared["row_limit"],
            question=prepared["question"],
            output_mode=prepared["output_mode"],
        )
        if prepared.get("optimizations_applied"):
            result["optimizations_applied"] = prepared["optimizations_applied"]
        if prepared.get("optimization_warnings"):
            result["optimization_warnings"] = prepared["optimization_warnings"]

        # Cache results so display_query can reference them by ID
        if result.get("status") == "ok" and result.get("output"):
            rid = str(uuid.uuid4())[:8]
            table = result["output"].get("table", {})
            self._result_cache[rid] = {
                "columns": table.get("columns", []),
                "rows": table.get("rows", []),
                "sql": prepared["normalized_sql"],
                "question": prepared["question"],
            }
            result["result_id"] = rid
            # Keep cache bounded
            if len(self._result_cache) > 20:
                oldest = next(iter(self._result_cache))
                del self._result_cache[oldest]

        return result

    def _start_query(self, arguments: Dict[str, Any]) -> dict:
        sql = arguments.get("sql")
        if not isinstance(sql, str):
            raise ToolError("sql is required")

        prepared = self._prepare_query(arguments, sql)
        if "needs_confirmation" in prepared:
            return prepared["needs_confirmation"]

        def _work() -> dict:
            return self._execute_query(
                normalized_sql=prepared["normalized_sql"],
                referenced_objects=prepared["referenced_objects"],
                row_limit=prepared["row_limit"],
                question=prepared["question"],
                output_mode=prepared["output_mode"],
            )

        job_id = self._jobs.start(prepared["normalized_sql"], _work)
        return {
            "status": "accepted",
            "job_id": job_id,
            "normalized_sql": prepared["normalized_sql"],
            "referenced_objects": prepared["referenced_objects"],
            "message": "Query accepted for async execution. Poll get_query_status/get_query_results.",
        }

    def _get_query_status(self, arguments: Dict[str, Any]) -> dict:
        job_id = arguments.get("job_id")
        if not isinstance(job_id, str) or not job_id.strip():
            raise ToolError("job_id is required")
        status = self._jobs.get_status(job_id)
        if status is None:
            raise ToolError(f"unknown job_id: {job_id}")
        return status

    def _get_query_results(self, arguments: Dict[str, Any]) -> dict:
        job_id = arguments.get("job_id")
        if not isinstance(job_id, str) or not job_id.strip():
            raise ToolError("job_id is required")
        result = self._jobs.get_result(job_id)
        if result is None:
            raise ToolError(f"unknown job_id: {job_id}")
        return result

    def _display_query(self, arguments: Dict[str, Any]) -> dict:
        # Option 1: result_id from a previous run_query (preferred — no LLM passthrough)
        result_id = arguments.get("result_id")
        if result_id:
            cached = self._result_cache.get(str(result_id))
            if not cached:
                raise ToolError(f"result_id {result_id!r} not found — it may have expired")
            columns = cached["columns"]
            rows = cached["rows"]
            question = arguments.get("question") or cached.get("question", "")
            sql = cached.get("sql", "")
        else:
            # Option 2: columns + rows passed directly (small datasets)
            columns = arguments.get("columns")
            rows = arguments.get("rows")
            if not isinstance(columns, list) or not isinstance(rows, list):
                raise ToolError("Either result_id or columns+rows is required")
            question = arguments.get("question") or ""
            sql = arguments.get("sql") or ""

        output = self._output.compose(
            question=question,
            columns=columns,
            rows=rows,
            output_mode="auto",
        )
        return {
            "status": "ok",
            "message": "Displaying results.",
            "normalized_sql": sql,
            "output": output,
        }

    def _display_sql(self, arguments: Dict[str, Any]) -> dict:
        sql = arguments.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise ToolError("sql is required")
        return {
            "sql": sql.strip(),
            "title": arguments.get("title") or "Generated SQL",
            "description": arguments.get("description") or "",
            "domain": arguments.get("domain") or "",
            "confidence": arguments.get("confidence"),
            "complexity": arguments.get("complexity") or "",
        }

    def _prepare_query(self, arguments: Dict[str, Any], sql: str) -> dict:
        policy_result = self._policy.validate(sql)
        approved = bool(arguments.get("approved", False))
        if self._session.needs_confirmation(approved=approved):
            return {
                "needs_confirmation": {
                    "status": "needs_confirmation",
                    "message": (
                        "Query execution requires confirmation. Re-run with approved=true, "
                        "or call set_session_approval(mode=\"approve-all\")."
                    ),
                    "normalized_sql": policy_result.normalized_sql,
                    "referenced_objects": list(policy_result.referenced_objects),
                }
            }

        row_limit = int(arguments.get("row_limit") or self._config.max_rows)
        row_limit = max(1, min(row_limit, self._config.max_rows))
        output_mode = arguments.get("output_mode") or self._config.default_output_mode
        question = arguments.get("question") or ""

        # Run pre-execution optimizer
        opt = optimize_query(
            sql=policy_result.normalized_sql,
            question=question,
            config=self._config,
            executor=self._executor,
        )

        result = {
            "normalized_sql": opt.sql,
            "referenced_objects": list(policy_result.referenced_objects),
            "row_limit": row_limit,
            "output_mode": output_mode,
            "question": question,
        }
        if opt.applied:
            result["optimizations_applied"] = opt.applied
        if opt.warnings:
            result["optimization_warnings"] = opt.warnings
        return result

    def _execute_query(
        self,
        normalized_sql: str,
        referenced_objects: List[str],
        row_limit: int,
        question: str,
        output_mode: str,
    ) -> dict:
        engine = self._engine
        started = time.time()
        entities = [obj.split(".")[-1].upper() for obj in referenced_objects]
        if not entities:
            entities = extract_entities_from_sql(normalized_sql)
        signature = engine.sql_signature(normalized_sql, entities, engine.estimate_complexity(normalized_sql))
        try:
            result = self._executor.run_query(normalized_sql, row_limit)
        except Exception:
            self._feedback.record(signature, success=False, execution_seconds=time.time() - started)
            raise

        self._feedback.record(signature, success=(result.status == "ok"), execution_seconds=result.execution_seconds)
        warnings = self._budget.record(result.credits_used)

        payload: dict = {
            "status": result.status,
            "message": result.message,
            "query_id": result.query_id,
            "execution_seconds": round(result.execution_seconds, 4),
            "normalized_sql": normalized_sql,
            "referenced_objects": referenced_objects,
            "budget_signal_source": result.budget_signal_source,
            "query_metrics": result.query_metrics,
            "budget_status": self._budget.status(),
            "new_budget_warnings": warnings,
        }
        if result.status == "ok":
            payload["output"] = self._output.compose(
                question=question,
                columns=result.columns,
                rows=result.rows,
                output_mode=output_mode,
            )
            diagnostics = engine.diagnose_no_data(
                output=payload["output"],
                normalized_sql=normalized_sql,
                question=question,
            )
            if diagnostics is not None:
                payload["result_quality"] = "no_data"
                payload["no_data_diagnostics"] = diagnostics
                payload["auto_refine"] = engine.build_auto_refine_payload(question, normalized_sql)
        return payload

    # ------------------------------------------------------------------
    # Session / governance tools
    # ------------------------------------------------------------------

    def _get_planner_feedback(self, _arguments: Dict[str, Any]) -> dict:
        return {"feedback": self._feedback.snapshot()}

    def _set_session_approval(self, arguments: Dict[str, Any]) -> dict:
        mode = arguments.get("mode")
        if not isinstance(mode, str):
            raise ToolError("mode is required")
        self._session.set_approval_mode(mode)
        return {
            "approval_mode": self._session.approval_mode,
            "require_query_confirmation": self._session.require_query_confirmation,
        }

    def _get_budget_status(self, _arguments: Dict[str, Any]) -> dict:
        return self._budget.status()

    # ------------------------------------------------------------------
    # Insights discovery
    # ------------------------------------------------------------------

    def _discover_insights(self, arguments: Dict[str, Any]) -> dict:
        if not self._config.enable_query_execution:
            return {
                "status": "execution_disabled",
                "message": "Insights discovery requires query execution (ENABLE_QUERY_EXECUTION=true).",
                "findings": [],
                "domains_scanned": [],
                "queries_run": 0,
                "queries_failed": 0,
                "scan_seconds": 0.0,
            }

        requested = arguments.get("domains")
        if requested:
            domains = [d.upper() for d in requested]
            for d in domains:
                if d not in self._config.allowed_domains:
                    raise ToolError(f"Domain {d!r} is not in ALLOWED_DOMAINS")
        else:
            domains = list(self._config.allowed_domains)

        from dataclasses import asdict
        findings, stats = run_diagnostics(
            executor=self._executor,
            config=self._config,
            allowed_domains=domains,
        )
        return {
            "status": "ok",
            "findings": [asdict(f) for f in findings],
            **stats,
        }

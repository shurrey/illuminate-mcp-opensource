"""Snowflake execution adapter (phase-1 baseline)."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Sequence

from .config import AppConfig
from .exceptions import ToolError
from .snowflake_conn import create_connection


@dataclass(frozen=True)
class QueryResult:
    status: str
    columns: Sequence[str]
    rows: Sequence[Sequence]
    query_id: str | None
    execution_seconds: float
    credits_used: float
    message: str
    budget_signal_source: str
    query_metrics: dict


@dataclass(frozen=True)
class ProbeResult:
    status: str
    has_rows: bool | None
    execution_seconds: float
    message: str


class SnowflakeExecutor:
    def __init__(self, config: AppConfig):
        self._config = config

    def run_query(self, sql: str, row_limit: int) -> QueryResult:
        if not self._config.enable_query_execution:
            return QueryResult(
                status="execution_disabled",
                columns=(),
                rows=(),
                query_id=None,
                execution_seconds=0.0,
                credits_used=0.0,
                message="Query execution is disabled (ENABLE_QUERY_EXECUTION=false).",
                budget_signal_source="disabled",
                query_metrics={},
            )

        started = time.time()
        connection = create_connection(self._config, {
            "QUERY_TAG": "illuminate_mcp:run_query",
            "STATEMENT_TIMEOUT_IN_SECONDS": self._config.statement_timeout_seconds,
        })

        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql)
                rows = cursor.fetchmany(row_limit)
                columns = [column[0] for column in (cursor.description or [])]
                query_id = getattr(cursor, "sfqid", None)
            finally:
                cursor.close()
            metrics = self._fetch_query_metrics(connection, query_id)
        finally:
            connection.close()

        execution_seconds = time.time() - started
        cloud_credits = float(metrics.get("credits_used_cloud_services", 0.0) or 0.0)
        estimated_warehouse_credits = self._estimate_warehouse_credits(metrics, execution_seconds)
        credits_used = cloud_credits
        signal_source = str(metrics.get("source", "none"))
        if credits_used <= 0 and estimated_warehouse_credits > 0:
            credits_used = estimated_warehouse_credits
            signal_source = "warehouse_estimate"

        metrics["estimated_warehouse_credits"] = round(estimated_warehouse_credits, 6)
        return QueryResult(
            status="ok",
            columns=columns,
            rows=rows,
            query_id=query_id,
            execution_seconds=execution_seconds,
            credits_used=credits_used,
            message="Query executed successfully.",
            budget_signal_source=signal_source,
            query_metrics=metrics,
        )

    def run_probe_exists(self, sql: str, timeout_seconds: int) -> ProbeResult:
        if not self._config.enable_query_execution:
            return ProbeResult(
                status="probe_disabled",
                has_rows=None,
                execution_seconds=0.0,
                message="Planner probes disabled because query execution is off.",
            )

        started = time.time()
        probe_sql = self._build_exists_probe(sql)
        connection = create_connection(self._config, {
            "QUERY_TAG": "illuminate_mcp:planner_probe",
            "STATEMENT_TIMEOUT_IN_SECONDS": timeout_seconds,
        })

        try:
            cursor = connection.cursor()
            try:
                cursor.execute(probe_sql)
                row = cursor.fetchone()
                columns = [column[0] for column in (cursor.description or [])]
                has_rows = self._infer_probe_has_rows(row, columns)
            finally:
                cursor.close()
        except Exception as exc:
            return ProbeResult(
                status="probe_failed",
                has_rows=None,
                execution_seconds=time.time() - started,
                message=f"Probe failed: {exc}",
            )
        finally:
            connection.close()

        return ProbeResult(
            status="ok",
            has_rows=has_rows,
            execution_seconds=time.time() - started,
            message="Probe completed.",
        )

    @staticmethod
    def _build_exists_probe(sql: str) -> str:
        normalized = sql.strip().rstrip(";")
        return f"SELECT * FROM ({normalized}) AS probe_q LIMIT 1"

    def _fetch_query_metrics(self, connection: Any, query_id: str | None) -> dict:
        if not query_id or not self._is_safe_query_id(query_id):
            return {"source": "none", "status": "missing_query_id"}

        sql = (
            "SELECT QUERY_ID, TOTAL_ELAPSED_TIME, BYTES_SCANNED, ROWS_PRODUCED, "
            "CREDITS_USED_CLOUD_SERVICES "
            "FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_SESSION(RESULT_LIMIT => 100)) "
            f"WHERE QUERY_ID = '{query_id}' "
            "ORDER BY START_TIME DESC LIMIT 1"
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(sql)
                row = cursor.fetchone()
                columns = [column[0] for column in (cursor.description or [])]
            finally:
                cursor.close()
        except Exception as exc:
            return {
                "source": "query_history_by_session",
                "status": "unavailable",
                "message": str(exc),
            }

        if not row:
            return {
                "source": "query_history_by_session",
                "status": "not_found",
            }
        return self._normalize_query_history_row(columns, row)

    @staticmethod
    def _normalize_query_history_row(columns: Sequence[str], row: Sequence) -> dict:
        mapping = {str(col).upper(): value for col, value in zip(columns, row)}
        return {
            "source": "query_history_by_session",
            "status": "ok",
            "query_id": mapping.get("QUERY_ID"),
            "elapsed_ms": int(mapping.get("TOTAL_ELAPSED_TIME") or 0),
            "bytes_scanned": int(mapping.get("BYTES_SCANNED") or 0),
            "rows_produced": int(mapping.get("ROWS_PRODUCED") or 0),
            "credits_used_cloud_services": float(mapping.get("CREDITS_USED_CLOUD_SERVICES") or 0.0),
        }

    def _estimate_warehouse_credits(self, metrics: dict, execution_seconds: float) -> float:
        rate = float(self._config.warehouse_credits_per_hour or 0.0)
        if rate <= 0:
            return 0.0

        elapsed_ms = int(metrics.get("elapsed_ms") or 0)
        seconds = (elapsed_ms / 1000.0) if elapsed_ms > 0 else max(0.0, float(execution_seconds))
        return max(0.0, (seconds / 3600.0) * rate)

    @staticmethod
    def _is_safe_query_id(query_id: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]+", query_id))

    @staticmethod
    def _infer_probe_has_rows(row: Sequence | None, columns: Sequence[str]) -> bool:
        if not row:
            return False

        upper_cols = [str(col).upper() for col in columns]
        if "RECORD_COUNT" in upper_cols:
            idx = upper_cols.index("RECORD_COUNT")
            try:
                value = row[idx]
                if value is None:
                    return False
                return float(value) > 0.0
            except Exception:
                return True

        return True

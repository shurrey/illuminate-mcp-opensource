"""Environment-backed application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

from .exceptions import ConfigError

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_APPROVAL_MODES = {"per-query", "approve-all"}
_OUTPUT_MODES = {"auto", "text", "table", "viz"}


def _as_csv(raw: str | None, default: Sequence[str]) -> Tuple[str, ...]:
    if raw is None or raw.strip() == "":
        return tuple(default)
    values = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(values or default)


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ConfigError(f"Invalid boolean value: {raw!r}")


def _as_int(raw: str | None, default: int, field_name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid integer for {field_name}: {raw!r}") from exc


def _as_float(raw: str | None, default: float, field_name: str) -> float:
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Invalid number for {field_name}: {raw!r}") from exc


def _normalize_snowflake_account(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""

    if value.startswith("https://"):
        value = value[len("https://") :]
    elif value.startswith("http://"):
        value = value[len("http://") :]

    value = value.split("/", 1)[0]
    if value.endswith(".snowflakecomputing.com"):
        value = value[: -len(".snowflakecomputing.com")]
    return value


@dataclass(frozen=True)
class AppConfig:
    snowflake_account: str
    snowflake_user: str
    snowflake_password: str
    snowflake_role: str
    snowflake_warehouse: str
    snowflake_database: str

    allowed_domains: Tuple[str, ...]
    allowed_schemas: Tuple[str, ...]
    allowed_tables: Tuple[str, ...]

    max_rows: int
    statement_timeout_seconds: int
    require_query_confirmation: bool
    default_session_approval_mode: str

    monthly_credit_budget: float
    budget_warning_thresholds: Tuple[int, ...]

    default_output_mode: str
    max_text_summary_length: int

    enable_query_execution: bool
    enable_metadata_introspection: bool
    metadata_dictionary_query: str
    enable_persistent_feedback: bool
    feedback_store_path: str
    enable_learn_schema: bool
    enable_planner_probes: bool
    planner_probe_timeout_seconds: int
    planner_max_probes: int
    warehouse_credits_per_hour: float

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppConfig":
        enable_query_execution = _as_bool(env.get("ENABLE_QUERY_EXECUTION"), False)
        enable_learn_schema = _as_bool(env.get("ENABLE_LEARN_SCHEMA"), False)
        allowed_domains = _as_csv(env.get("ALLOWED_DOMAINS"), ("CDM_LMS", "CDM_TLM", "CDM_ALY"))
        allowed_schemas = _as_csv(env.get("ALLOWED_SCHEMAS"), ("CDM_LMS", "CDM_TLM", "CDM_ALY"))
        if enable_learn_schema:
            if "LEARN" not in allowed_domains:
                allowed_domains = allowed_domains + ("LEARN",)
            if "LEARN" not in allowed_schemas:
                allowed_schemas = allowed_schemas + ("LEARN",)
        config = cls(
            snowflake_account=_normalize_snowflake_account(
                env.get("SNOWFLAKE_ACCOUNT", "")
            ),
            snowflake_user=env.get("SNOWFLAKE_USER", "").strip(),
            snowflake_password=env.get("SNOWFLAKE_PASSWORD", "").strip(),
            snowflake_role=env.get("SNOWFLAKE_ROLE", "").strip(),
            snowflake_warehouse=env.get("SNOWFLAKE_WAREHOUSE", "").strip(),
            snowflake_database=env.get("SNOWFLAKE_DATABASE", "").strip(),
            allowed_domains=allowed_domains,
            allowed_schemas=allowed_schemas,
            allowed_tables=_as_csv(env.get("ALLOWED_TABLES"), ()),
            max_rows=_as_int(env.get("MAX_ROWS"), 1000, "MAX_ROWS"),
            statement_timeout_seconds=_as_int(
                env.get("STATEMENT_TIMEOUT_SECONDS"),
                120,
                "STATEMENT_TIMEOUT_SECONDS",
            ),
            require_query_confirmation=_as_bool(
                env.get("REQUIRE_QUERY_CONFIRMATION"),
                True,
            ),
            default_session_approval_mode=env.get(
                "DEFAULT_SESSION_APPROVAL_MODE",
                "per-query",
            ).strip(),
            monthly_credit_budget=_as_float(
                env.get("MONTHLY_CREDIT_BUDGET"),
                100.0,
                "MONTHLY_CREDIT_BUDGET",
            ),
            budget_warning_thresholds=tuple(
                _as_int(raw.strip(), 0, "BUDGET_WARNING_THRESHOLDS")
                for raw in _as_csv(env.get("BUDGET_WARNING_THRESHOLDS"), ("70", "85", "100"))
            ),
            default_output_mode=env.get("DEFAULT_OUTPUT_MODE", "auto").strip(),
            max_text_summary_length=_as_int(
                env.get("MAX_TEXT_SUMMARY_LENGTH"),
                1200,
                "MAX_TEXT_SUMMARY_LENGTH",
            ),
            enable_query_execution=enable_query_execution,
            enable_metadata_introspection=_as_bool(
                env.get("ENABLE_METADATA_INTROSPECTION"),
                False,
            ),
            metadata_dictionary_query=env.get("METADATA_DICTIONARY_QUERY", "").strip(),
            enable_persistent_feedback=_as_bool(
                env.get("ENABLE_PERSISTENT_FEEDBACK"),
                False,
            ),
            feedback_store_path=env.get(
                "FEEDBACK_STORE_PATH",
                ".planner_feedback.json",
            ).strip(),
            enable_learn_schema=enable_learn_schema,
            enable_planner_probes=_as_bool(
                env.get("ENABLE_PLANNER_PROBES"),
                enable_query_execution,
            ),
            planner_probe_timeout_seconds=_as_int(
                env.get("PLANNER_PROBE_TIMEOUT_SECONDS"),
                8,
                "PLANNER_PROBE_TIMEOUT_SECONDS",
            ),
            planner_max_probes=_as_int(
                env.get("PLANNER_MAX_PROBES"),
                2,
                "PLANNER_MAX_PROBES",
            ),
            warehouse_credits_per_hour=_as_float(
                env.get("WAREHOUSE_CREDITS_PER_HOUR"),
                0.0,
                "WAREHOUSE_CREDITS_PER_HOUR",
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if not self.allowed_domains:
            raise ConfigError("ALLOWED_DOMAINS must include at least one domain")
        if self.max_rows <= 0:
            raise ConfigError("MAX_ROWS must be greater than zero")
        if self.statement_timeout_seconds <= 0:
            raise ConfigError("STATEMENT_TIMEOUT_SECONDS must be greater than zero")
        if self.default_session_approval_mode not in _APPROVAL_MODES:
            raise ConfigError(
                "DEFAULT_SESSION_APPROVAL_MODE must be one of: "
                + ", ".join(sorted(_APPROVAL_MODES))
            )
        if self.default_output_mode not in _OUTPUT_MODES:
            raise ConfigError(
                "DEFAULT_OUTPUT_MODE must be one of: "
                + ", ".join(sorted(_OUTPUT_MODES))
            )
        if self.monthly_credit_budget <= 0:
            raise ConfigError("MONTHLY_CREDIT_BUDGET must be greater than zero")
        if not self.budget_warning_thresholds:
            raise ConfigError("BUDGET_WARNING_THRESHOLDS cannot be empty")
        if any(value <= 0 for value in self.budget_warning_thresholds):
            raise ConfigError("BUDGET_WARNING_THRESHOLDS must contain positive percentages")
        if tuple(sorted(set(self.budget_warning_thresholds))) != self.budget_warning_thresholds:
            raise ConfigError("BUDGET_WARNING_THRESHOLDS must be sorted unique values")

        if self.enable_query_execution or self.enable_metadata_introspection:
            required = {
                "SNOWFLAKE_ACCOUNT": self.snowflake_account,
                "SNOWFLAKE_USER": self.snowflake_user,
                "SNOWFLAKE_PASSWORD": self.snowflake_password,
                "SNOWFLAKE_ROLE": self.snowflake_role,
                "SNOWFLAKE_WAREHOUSE": self.snowflake_warehouse,
                "SNOWFLAKE_DATABASE": self.snowflake_database,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ConfigError(
                    "Enabled Snowflake features require values for: " + ", ".join(missing)
                )
        if self.enable_persistent_feedback and not self.feedback_store_path:
            raise ConfigError(
                "FEEDBACK_STORE_PATH is required when ENABLE_PERSISTENT_FEEDBACK=true"
            )
        if self.planner_probe_timeout_seconds <= 0:
            raise ConfigError("PLANNER_PROBE_TIMEOUT_SECONDS must be greater than zero")
        if self.planner_max_probes < 0:
            raise ConfigError("PLANNER_MAX_PROBES must be zero or greater")
        if self.enable_planner_probes and not self.enable_query_execution:
            raise ConfigError(
                "ENABLE_PLANNER_PROBES=true requires ENABLE_QUERY_EXECUTION=true"
            )
        if self.warehouse_credits_per_hour < 0:
            raise ConfigError("WAREHOUSE_CREDITS_PER_HOUR must be zero or greater")

    def public_settings(self) -> dict:
        return {
            "allowed_domains": list(self.allowed_domains),
            "allowed_schemas": list(self.allowed_schemas),
            "allowed_tables": list(self.allowed_tables),
            "max_rows": self.max_rows,
            "statement_timeout_seconds": self.statement_timeout_seconds,
            "require_query_confirmation": self.require_query_confirmation,
            "default_session_approval_mode": self.default_session_approval_mode,
            "monthly_credit_budget": self.monthly_credit_budget,
            "budget_warning_thresholds": list(self.budget_warning_thresholds),
            "default_output_mode": self.default_output_mode,
            "max_text_summary_length": self.max_text_summary_length,
            "enable_query_execution": self.enable_query_execution,
            "enable_metadata_introspection": self.enable_metadata_introspection,
            "metadata_dictionary_query_configured": bool(self.metadata_dictionary_query),
            "enable_persistent_feedback": self.enable_persistent_feedback,
            "feedback_store_path": self.feedback_store_path,
            "enable_learn_schema": self.enable_learn_schema,
            "enable_planner_probes": self.enable_planner_probes,
            "planner_probe_timeout_seconds": self.planner_probe_timeout_seconds,
            "planner_max_probes": self.planner_max_probes,
            "warehouse_credits_per_hour": self.warehouse_credits_per_hour,
        }

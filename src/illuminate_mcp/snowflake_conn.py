"""Shared Snowflake connection factory."""

from __future__ import annotations

from typing import Any, Dict

from .config import AppConfig


def create_connection(config: AppConfig, session_parameters: Dict[str, Any] | None = None) -> Any:
    """Create a Snowflake connection from AppConfig with optional session parameters."""
    try:
        import snowflake.connector  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "snowflake-connector-python is required for Snowflake connectivity"
        ) from exc

    params: Dict[str, Any] = {
        "account": config.snowflake_account,
        "user": config.snowflake_user,
        "password": config.snowflake_password,
        "role": config.snowflake_role,
        "warehouse": config.snowflake_warehouse,
        "database": config.snowflake_database,
    }
    if session_parameters:
        params["session_parameters"] = session_parameters

    return snowflake.connector.connect(**params)

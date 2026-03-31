"""Ephemeral per-process session state."""

from dataclasses import dataclass

from .exceptions import ToolError


@dataclass
class SessionState:
    require_query_confirmation: bool
    approval_mode: str

    def needs_confirmation(self, approved: bool = False) -> bool:
        if not self.require_query_confirmation:
            return False
        if self.approval_mode == "approve-all":
            return False
        return not approved

    def set_approval_mode(self, mode: str) -> None:
        if mode not in {"per-query", "approve-all"}:
            raise ToolError("approval mode must be 'per-query' or 'approve-all'")
        self.approval_mode = mode

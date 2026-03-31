"""Ephemeral budget tracker for session-level governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class BudgetTracker:
    monthly_credit_budget: float
    thresholds: List[int]
    consumed_credits: float = 0.0
    fired_thresholds: set = field(default_factory=set)

    def __init__(self, monthly_credit_budget: float, thresholds: Iterable[int]):
        self.monthly_credit_budget = monthly_credit_budget
        self.thresholds = list(thresholds)
        self.consumed_credits = 0.0
        self.fired_thresholds = set()

    def record(self, credits_used: float) -> List[int]:
        if credits_used <= 0:
            return []

        self.consumed_credits += credits_used
        percent_used = (self.consumed_credits / self.monthly_credit_budget) * 100

        newly_fired = []
        for threshold in self.thresholds:
            if percent_used >= threshold and threshold not in self.fired_thresholds:
                self.fired_thresholds.add(threshold)
                newly_fired.append(threshold)
        return newly_fired

    def status(self) -> dict:
        percent_used = (self.consumed_credits / self.monthly_credit_budget) * 100
        return {
            "monthly_credit_budget": self.monthly_credit_budget,
            "consumed_credits": round(self.consumed_credits, 4),
            "remaining_credits": round(self.monthly_credit_budget - self.consumed_credits, 4),
            "percent_used": round(percent_used, 2),
            "warning_thresholds": self.thresholds,
            "triggered_thresholds": sorted(self.fired_thresholds),
        }

"""
Pure budget arithmetic — no I/O, no Qt, trivially testable.
"""

from dataclasses import dataclass


@dataclass
class BudgetState:
    monthly_budget: float
    spent: float

    @property
    def remaining(self) -> float:
        return self.monthly_budget - self.spent

    @property
    def exceeded(self) -> bool:
        return self.remaining < 0

    @property
    def percent_used(self) -> float:
        if self.monthly_budget <= 0:
            return 0.0
        return min(self.spent / self.monthly_budget * 100, 100.0)

    def format_remaining(self) -> str:
        if self.exceeded:
            return f"-${abs(self.remaining):.2f}"
        return f"${self.remaining:.2f}"

    def format_spent(self) -> str:
        return f"${self.spent:.2f}"

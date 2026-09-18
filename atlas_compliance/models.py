"""Domain models for the Atlas compliance engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DecisionState(StrEnum):
    """Supported compliance decision states."""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class Employee:
    """Minimum employee fields needed for minimum-wage evaluation."""

    employee_id: str | None
    work_country: str | None
    work_state: str | None
    work_location_code: str | None
    pay_basis: str | None
    hourly_rate_ast: Decimal | None
    annual_salary_ast: Decimal | None
    scheduled_hours_per_week: Decimal | None
    currency: str | None
    employment_status: str | None
    minimum_wage_coverage: str | None


@dataclass(frozen=True, slots=True)
class MinimumWageRule:
    """An approved, versioned minimum-wage rule."""

    jurisdiction: str
    amount: Decimal
    currency: str
    unit: str
    effective_date: date
    rule_id: str
    coverage: str

    def public_dict(self) -> dict[str, str]:
        """Return stable fields suitable for an audit trace."""
        return {
            "jurisdiction": self.jurisdiction,
            "amount": f"{self.amount.quantize(Decimal('0.01'))}",
            "currency": self.currency,
            "unit": self.unit,
            "effective_date": self.effective_date.isoformat(),
            "rule_id": self.rule_id,
            "coverage": self.coverage,
        }


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Auditable output of one employee evaluation."""

    employee_id: str | None
    evaluation_date: date
    work_jurisdiction: str | None
    actual_hourly_wage: Decimal | None
    currency: str | None
    candidate_applicable_rules: tuple[MinimumWageRule, ...]
    controlling_minimum_wage: Decimal | None
    controlling_jurisdiction: str | None
    controlling_rule_version: str | None
    decision_state: DecisionState
    hourly_shortfall: Decimal | None
    estimated_weekly_underpayment: Decimal | None
    explanation: tuple[str, ...]
    evaluation_timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result, formatting displayed monetary values to cents."""
        def money(value: Decimal | None) -> str | None:
            return None if value is None else f"{value:.2f}"

        return {
            "employee_id": self.employee_id,
            "evaluation_date": self.evaluation_date.isoformat(),
            "work_jurisdiction": self.work_jurisdiction,
            "actual_hourly_wage": money(self.actual_hourly_wage),
            "currency": self.currency,
            "candidate_applicable_rules": [
                rule.public_dict() for rule in self.candidate_applicable_rules
            ],
            "controlling_minimum_wage": money(self.controlling_minimum_wage),
            "controlling_jurisdiction": self.controlling_jurisdiction,
            "controlling_rule_version": self.controlling_rule_version,
            "decision_state": self.decision_state.value,
            "hourly_shortfall": money(self.hourly_shortfall),
            "estimated_weekly_underpayment": money(
                self.estimated_weekly_underpayment
            ),
            "explanation": list(self.explanation),
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
        }

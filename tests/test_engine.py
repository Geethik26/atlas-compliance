"""Tests for deterministic minimum-wage decisions."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from atlas_compliance.engine import evaluate_employee
from atlas_compliance.models import DecisionState, Employee, MinimumWageRule
from atlas_compliance.rules import load_rules

EVALUATION_DATE = date(2026, 9, 16)


@pytest.fixture
def rules() -> list[MinimumWageRule]:
    return [
        MinimumWageRule(
            "Asteria Federal",
            Decimal("12.82"),
            "AST",
            "hour",
            EVALUATION_DATE,
            "AFWA-MW-2026.1",
            "Covered, nonexempt employees",
        ),
        MinimumWageRule(
            "Bellwether",
            Decimal("16.87"),
            "AST",
            "hour",
            EVALUATION_DATE,
            "BDL-MW-2026.1",
            "Covered, nonexempt employees",
        ),
    ]


@pytest.fixture
def employee() -> Employee:
    return Employee(
        employee_id="TEST-1",
        work_country="Asteria",
        work_state="Federal Territory",
        work_location_code="FT-1",
        pay_basis="Hourly",
        hourly_rate_ast=Decimal("13.00"),
        annual_salary_ast=None,
        scheduled_hours_per_week=Decimal("40"),
        currency="AST",
        employment_status="Active",
        minimum_wage_coverage="Covered",
    )


def test_federal_below_minimum(employee: Employee, rules: list[MinimumWageRule]) -> None:
    result = evaluate_employee(
        replace(employee, hourly_rate_ast=Decimal("12.00")), rules, EVALUATION_DATE
    )
    assert result.decision_state is DecisionState.NON_COMPLIANT
    assert result.hourly_shortfall == Decimal("0.82")
    assert result.estimated_weekly_underpayment == Decimal("32.80")


def test_federal_above_minimum(employee: Employee, rules: list[MinimumWageRule]) -> None:
    result = evaluate_employee(employee, rules, EVALUATION_DATE)
    assert result.decision_state is DecisionState.COMPLIANT


def test_exact_equality_is_compliant(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(employee, hourly_rate_ast=Decimal("12.82")), rules, EVALUATION_DATE
    )
    assert result.decision_state is DecisionState.COMPLIANT
    assert result.hourly_shortfall == Decimal("0.00")


def test_bellwether_considers_both_rules(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(employee, work_state="Bellwether", hourly_rate_ast=Decimal("18")),
        rules,
        EVALUATION_DATE,
    )
    assert {rule.rule_id for rule in result.candidate_applicable_rules} == {
        "AFWA-MW-2026.1",
        "BDL-MW-2026.1",
    }


def test_bellwether_state_rate_controls(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(employee, work_state="Bellwether", hourly_rate_ast=Decimal("15")),
        rules,
        EVALUATION_DATE,
    )
    assert result.decision_state is DecisionState.NON_COMPLIANT
    assert result.controlling_jurisdiction == "Bellwether"
    assert result.controlling_minimum_wage == Decimal("16.87")


def test_salaried_employee_conversion(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(
            employee,
            pay_basis="Annual Salary",
            hourly_rate_ast=None,
            annual_salary_ast=Decimal("26665.60"),
        ),
        rules,
        EVALUATION_DATE,
    )
    assert result.actual_hourly_wage == Decimal("12.82")
    assert result.decision_state is DecisionState.COMPLIANT


def test_missing_wage_data(employee: Employee, rules: list[MinimumWageRule]) -> None:
    result = evaluate_employee(
        replace(employee, hourly_rate_ast=None), rules, EVALUATION_DATE
    )
    assert result.decision_state is DecisionState.INSUFFICIENT_DATA


def test_missing_scheduled_hours_for_salary(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(
            employee,
            pay_basis="Annual Salary",
            hourly_rate_ast=None,
            annual_salary_ast=Decimal("50000"),
            scheduled_hours_per_week=None,
        ),
        rules,
        EVALUATION_DATE,
    )
    assert result.decision_state is DecisionState.INSUFFICIENT_DATA


def test_future_rule_not_active(employee: Employee) -> None:
    future = MinimumWageRule(
        "Asteria Federal",
        Decimal("20"),
        "AST",
        "hour",
        date(2026, 9, 17),
        "FUTURE",
        "Covered, nonexempt employees",
    )
    result = evaluate_employee(employee, [future], EVALUATION_DATE)
    assert result.decision_state is DecisionState.INSUFFICIENT_DATA
    assert result.candidate_applicable_rules == ()


def test_missing_applicable_rule(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(employee, work_state="Bellwether"), rules[:1], EVALUATION_DATE
    )
    assert result.decision_state is DecisionState.INSUFFICIENT_DATA


def test_deterministic_repeated_evaluation(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    first = evaluate_employee(employee, rules, EVALUATION_DATE)
    second = evaluate_employee(employee, rules, EVALUATION_DATE)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_conflicting_currency_requires_review(
    employee: Employee, rules: list[MinimumWageRule]
) -> None:
    result = evaluate_employee(
        replace(employee, currency="USD"), rules, EVALUATION_DATE
    )
    assert result.decision_state is DecisionState.REVIEW_REQUIRED


def test_seeded_rule_provenance_is_exposed_in_result(employee: Employee) -> None:
    rules = load_rules(Path("data/approved_rules.json"))
    result = evaluate_employee(employee, rules, EVALUATION_DATE)
    serialized = result.to_dict()
    assert serialized["controlling_source_url"] == (
        "https://asterian-federal-wage-site.vercel.app/"
    )
    assert serialized["controlling_evidence_text"] == (
        "Assignment-provided approved baseline: 12.82 AST per hour effective "
        "2026-09-16."
    )
    assert serialized["candidate_applicable_rules"][0]["source_url"] == (
        serialized["controlling_source_url"]
    )

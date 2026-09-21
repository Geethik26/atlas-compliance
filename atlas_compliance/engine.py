"""Deterministic minimum-wage compliance decision engine."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from .models import DecisionState, Employee, EvaluationResult, MinimumWageRule

CENT = Decimal("0.01")
WEEKS_PER_YEAR = Decimal("52")


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _result(
    employee: Employee,
    evaluation_date: date,
    jurisdiction: str | None,
    rules: tuple[MinimumWageRule, ...],
    state: DecisionState,
    trace: list[str],
    *,
    actual: Decimal | None = None,
    controlling: MinimumWageRule | None = None,
    shortfall: Decimal | None = None,
    weekly: Decimal | None = None,
) -> EvaluationResult:
    return EvaluationResult(
        employee_id=employee.employee_id,
        evaluation_date=evaluation_date,
        work_jurisdiction=jurisdiction,
        actual_hourly_wage=None if actual is None else _cents(actual),
        currency=employee.currency,
        candidate_applicable_rules=rules,
        controlling_minimum_wage=(
            None if controlling is None else _cents(controlling.amount)
        ),
        controlling_jurisdiction=(
            None if controlling is None else controlling.jurisdiction
        ),
        controlling_rule_version=None if controlling is None else controlling.rule_id,
        controlling_source_url=(
            None if controlling is None else controlling.source_url
        ),
        controlling_source_snapshot_path=(
            None if controlling is None else controlling.source_snapshot_path
        ),
        controlling_source_hash=(
            None if controlling is None else controlling.source_hash
        ),
        controlling_evidence_text=(
            None if controlling is None else controlling.evidence_text
        ),
        controlling_proposal_id=(
            None if controlling is None else controlling.proposal_id
        ),
        decision_state=state,
        hourly_shortfall=None if shortfall is None else _cents(shortfall),
        estimated_weekly_underpayment=None if weekly is None else _cents(weekly),
        explanation=tuple(trace),
        # A deterministic timestamp preserves reproducibility for identical inputs.
        evaluation_timestamp=datetime.combine(
            evaluation_date, time.min, tzinfo=timezone.utc
        ),
    )


def evaluate_employee(
    employee: Employee,
    rules: list[MinimumWageRule],
    evaluation_date: date,
) -> EvaluationResult:
    """Evaluate one employee against effective approved minimum-wage rules."""
    trace = [f"Evaluation date: {evaluation_date.isoformat()}."]
    jurisdiction: str | None = None

    missing = [
        name
        for name, value in (
            ("employee_id", employee.employee_id),
            ("work_country", employee.work_country),
            ("work_state", employee.work_state),
            ("work_location_code", employee.work_location_code),
            ("pay_basis", employee.pay_basis),
            ("currency", employee.currency),
            ("employment_status", employee.employment_status),
            ("minimum_wage_coverage", employee.minimum_wage_coverage),
            ("scheduled_hours_per_week", employee.scheduled_hours_per_week),
        )
        if value is None
    ]
    if missing:
        trace.append(f"Required data missing: {', '.join(missing)}.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            (),
            DecisionState.INSUFFICIENT_DATA,
            trace,
        )

    assert employee.work_country is not None
    assert employee.work_state is not None
    assert employee.scheduled_hours_per_week is not None
    if employee.work_country != "Asteria":
        trace.append(f"Unsupported work country: {employee.work_country}.")
        return _result(
            employee, evaluation_date, None, (), DecisionState.REVIEW_REQUIRED, trace
        )
    if employee.work_state == "Federal Territory":
        jurisdiction = "Federal Territory"
        eligible_jurisdictions = {"Asteria Federal"}
    elif employee.work_state == "Bellwether":
        jurisdiction = "Bellwether"
        eligible_jurisdictions = {"Asteria Federal", "Bellwether"}
    else:
        trace.append(f"Unsupported work state: {employee.work_state}.")
        return _result(
            employee, evaluation_date, None, (), DecisionState.REVIEW_REQUIRED, trace
        )
    trace.append(f"Resolved work jurisdiction: {jurisdiction}.")

    if employee.employment_status != "Active":
        trace.append("Employment status is not Active; manual review is required.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            (),
            DecisionState.REVIEW_REQUIRED,
            trace,
        )
    if employee.minimum_wage_coverage != "Covered":
        trace.append(
            "Coverage is not an unambiguous Covered status; manual review is required."
        )
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            (),
            DecisionState.REVIEW_REQUIRED,
            trace,
        )
    if employee.scheduled_hours_per_week <= 0:
        trace.append("Scheduled hours must be greater than zero.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            (),
            DecisionState.REVIEW_REQUIRED,
            trace,
        )

    effective_rules = tuple(
        sorted(
            (
                rule
                for rule in rules
                if rule.jurisdiction in eligible_jurisdictions
                and rule.effective_date <= evaluation_date
            ),
            key=lambda rule: (rule.jurisdiction, rule.effective_date, rule.rule_id),
        )
    )
    latest_by_jurisdiction: dict[str, list[MinimumWageRule]] = {}
    for name in eligible_jurisdictions:
        jurisdiction_rules = [
            rule for rule in effective_rules if rule.jurisdiction == name
        ]
        if jurisdiction_rules:
            latest_date = max(rule.effective_date for rule in jurisdiction_rules)
            latest_by_jurisdiction[name] = [
                rule
                for rule in jurisdiction_rules
                if rule.effective_date == latest_date
            ]
    candidates = tuple(
        sorted(
            (rule for group in latest_by_jurisdiction.values() for rule in group),
            key=lambda rule: (rule.jurisdiction, rule.effective_date, rule.rule_id),
        )
    )
    trace.append(
        "Effective candidate rules: "
        + (", ".join(rule.rule_id for rule in candidates) or "none")
        + "."
    )
    expected = eligible_jurisdictions
    present = {rule.jurisdiction for rule in candidates}
    if present != expected:
        trace.append(
            "No complete approved rule set exists for all applicable jurisdictions."
        )
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.INSUFFICIENT_DATA,
            trace,
        )
    if any(rule.currency != employee.currency for rule in candidates):
        trace.append("Employee and applicable rule currencies conflict.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.REVIEW_REQUIRED,
            trace,
        )
    if any(rule.unit != "hour" for rule in candidates):
        trace.append("An applicable rule has an unsupported wage unit.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.REVIEW_REQUIRED,
            trace,
        )
    if any(rule.coverage != "Covered, nonexempt employees" for rule in candidates):
        trace.append("An applicable rule has missing or conflicting coverage data.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.REVIEW_REQUIRED,
            trace,
        )
    duplicate_jurisdictions = {
        name for name in present if sum(r.jurisdiction == name for r in candidates) > 1
    }
    if duplicate_jurisdictions:
        trace.append("Conflicting concurrent rule versions require manual review.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.REVIEW_REQUIRED,
            trace,
        )

    controlling = max(candidates, key=lambda rule: rule.amount)
    trace.append(
        f"Controlling rule {controlling.rule_id} is the highest applicable rate "
        f"at {controlling.amount} {controlling.currency}/hour."
    )

    if employee.pay_basis == "Hourly":
        if employee.hourly_rate_ast is None:
            trace.append("Hourly wage is missing.")
            return _result(
                employee,
                evaluation_date,
                jurisdiction,
                candidates,
                DecisionState.INSUFFICIENT_DATA,
                trace,
                controlling=controlling,
            )
        actual = employee.hourly_rate_ast
        trace.append(f"Used stated hourly wage: {actual} {employee.currency}/hour.")
    elif employee.pay_basis == "Annual Salary":
        if employee.annual_salary_ast is None:
            trace.append("Annual salary is missing.")
            return _result(
                employee,
                evaluation_date,
                jurisdiction,
                candidates,
                DecisionState.INSUFFICIENT_DATA,
                trace,
                controlling=controlling,
            )
        actual = employee.annual_salary_ast / (
            WEEKS_PER_YEAR * employee.scheduled_hours_per_week
        )
        trace.append(
            "Prototype salary conversion: annual salary / "
            f"(52 * {employee.scheduled_hours_per_week} scheduled weekly hours) "
            f"= {actual} {employee.currency}/hour."
        )
    else:
        trace.append(f"Unsupported pay basis: {employee.pay_basis}.")
        return _result(
            employee,
            evaluation_date,
            jurisdiction,
            candidates,
            DecisionState.REVIEW_REQUIRED,
            trace,
            controlling=controlling,
        )

    raw_shortfall = max(Decimal("0"), controlling.amount - actual)
    if raw_shortfall == 0:
        trace.append("Actual hourly wage meets or exceeds the controlling rate.")
        state = DecisionState.COMPLIANT
    else:
        trace.append("Actual hourly wage is below the controlling rate.")
        state = DecisionState.NON_COMPLIANT
    return _result(
        employee,
        evaluation_date,
        jurisdiction,
        candidates,
        state,
        trace,
        actual=actual,
        controlling=controlling,
        shortfall=raw_shortfall,
        weekly=raw_shortfall * employee.scheduled_hours_per_week,
    )

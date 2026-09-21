"""Tests for privacy-minimized JSON and CSV compliance exports."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from atlas_compliance.engine import evaluate_employee
from atlas_compliance.loader import load_employees
from atlas_compliance.models import EvaluationResult
from atlas_compliance.reporting import build_report, write_csv_report, write_json_report
from atlas_compliance.rules import load_rules


@pytest.fixture
def export_dir() -> Path:
    path = Path.cwd() / f".monitor-test-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


@pytest.fixture
def results() -> list[EvaluationResult]:
    employees = load_employees(Path("data/synthetic_employee_system_of_record.xlsx"))
    rules = load_rules(Path("data/demo_baseline_rules.json"))
    return [
        evaluate_employee(employee, rules, date(2026, 9, 16))
        for employee in employees
    ]


def test_json_report_contains_all_results_and_summary(
    results: list[EvaluationResult], export_dir: Path
) -> None:
    path = export_dir / "report.json"
    write_json_report(results, path)
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["record_count"] == 48
    assert report["decision_summary"] == {
        "COMPLIANT": 16,
        "NON_COMPLIANT": 32,
    }
    assert len(report["results"]) == 48


def test_csv_report_is_flat_and_complete(
    results: list[EvaluationResult], export_dir: Path
) -> None:
    path = export_dir / "report.csv"
    write_csv_report(results, path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 48
    assert rows[0]["employee_id"] == "AST-0001"
    assert json.loads(rows[0]["candidate_applicable_rules"])
    assert json.loads(rows[0]["explanation"])


def test_report_contains_no_unnecessary_employee_pii(
    results: list[EvaluationResult],
) -> None:
    serialized = json.dumps(build_report(results)).casefold()
    forbidden = (
        "national_id",
        "bank_account",
        "date_of_birth",
        "personal_email",
        "personal_phone",
        "home_address",
        "emergency_contact",
    )
    assert all(field not in serialized for field in forbidden)


"""End-to-end test for the reproducible fictional demonstration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from atlas_compliance.demo import run_demo


@pytest.fixture
def demo_output() -> Path:
    path = Path.cwd() / f".monitor-test-{uuid4().hex}"
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def test_reproducible_demo_runs_full_workflow(demo_output: Path) -> None:
    baseline = Path("data/demo_baseline_rules.json").read_bytes()
    summary = run_demo(demo_output)
    assert summary["simulation"] is True
    assert summary["first_monitoring_state"] == "FIRST_SNAPSHOT"
    assert summary["second_monitoring_state"] == "CHANGED"
    assert summary["proposal_initial_status"] == "REVIEW_REQUIRED"
    assert summary["approved_rule_id"] == "AFWA-2026-0042"
    assert summary["approved_amount"] == "13.25"
    assert summary["approved_effective_date"] == "2027-01-01"
    assert summary["targeted_employee_count"] == 48
    assert summary["changed_result_count"] > 0
    assert Path("data/demo_baseline_rules.json").read_bytes() == baseline

    audit_events = [
        json.loads(line)
        for line in (demo_output / "audit.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["event_type"] for event in audit_events] == [
        "SOURCE_INTERPRETED",
        "PROPOSAL_CREATED",
        "PROPOSAL_CREATED",
        "PROPOSAL_REVIEWED",
        "RULE_APPROVED",
        "EMPLOYEES_REEVALUATED",
    ]
    change_records = list(demo_output.rglob("*.change.json"))
    assert len(change_records) == 1
    assert "13.25 AST per hour" in change_records[0].read_text(encoding="utf-8")


def test_demo_refuses_to_overwrite_existing_output(demo_output: Path) -> None:
    demo_output.mkdir()
    with pytest.raises(FileExistsError):
        run_demo(demo_output)

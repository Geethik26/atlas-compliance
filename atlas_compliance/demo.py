"""Reproducible, isolated Atlas change-to-reevaluation demonstration."""

from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path

from .loader import load_employees
from .monitoring import (
    TRUSTED_SOURCES,
    FetchResponse,
    MonitoringResult,
    monitor_source,
)
from .workflow import (
    approve_proposal,
    discover_snapshot,
    reevaluate_affected_employees,
)

FIRST_FETCH = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
SECOND_FETCH = datetime(2026, 12, 15, 12, 5, tzinfo=timezone.utc)
APPROVAL_TIME = datetime(2026, 12, 15, 12, 10, tzinfo=timezone.utc)
EVALUATION_DATE = date(2027, 1, 1)


def _clock(timestamp: datetime) -> Callable[[], datetime]:
    return lambda: timestamp


def _local_fetch(content: bytes) -> Callable[..., FetchResponse]:
    def fetch(*_args: object, **_kwargs: object) -> FetchResponse:
        return FetchResponse(content=content, status=200)

    return fetch


def _require_snapshot(result: MonitoringResult) -> Path:
    if result.metadata is None:
        raise RuntimeError(f"Demo snapshot failed: {result.state.value}")
    return Path(result.metadata.snapshot_path)


def run_demo(
    output_dir: Path,
    *,
    fixture_dir: Path = Path("demo/fixtures"),
    baseline_registry: Path = Path("data/approved_rules.json"),
    employees_path: Path = Path("data/synthetic_employee_system_of_record.xlsx"),
) -> dict[str, object]:
    """Run the full workflow against tracked fictional fixtures.

    Args:
        output_dir: New directory that will receive isolated demo evidence.
        fixture_dir: Directory containing the before and after HTML fixtures.
        baseline_registry: Approved registry copied into the isolated output.
        employees_path: Synthetic employee workbook used for reevaluation.

    Returns:
        A JSON-compatible demonstration summary.

    Raises:
        FileExistsError: If the output directory already exists.
        RuntimeError: If monitoring or proposal discovery cannot complete.
    """
    output_dir.mkdir(parents=True, exist_ok=False)
    registry_path = output_dir / "approved_rules.json"
    proposal_path = output_dir / "proposed_rules.json"
    audit_path = output_dir / "audit.jsonl"
    reevaluation_path = output_dir / "reevaluation.json"
    summary_path = output_dir / "summary.json"
    shutil.copyfile(baseline_registry, registry_path)

    source = TRUSTED_SOURCES[0]
    before_content = (fixture_dir / "asteria_before.html").read_bytes()
    after_content = (fixture_dir / "asteria_after.html").read_bytes()
    first = monitor_source(
        source,
        output_dir,
        fetcher=_local_fetch(before_content),
        now=_clock(FIRST_FETCH),
    )
    second = monitor_source(
        source,
        output_dir,
        fetcher=_local_fetch(after_content),
        now=_clock(SECOND_FETCH),
    )
    snapshot_path = output_dir / _require_snapshot(second)
    proposals = discover_snapshot(
        source,
        snapshot_path,
        proposal_path,
        audit_path,
        now=SECOND_FETCH,
    )
    final_rule = next(
        (
            proposal
            for proposal in proposals
            if proposal.source_notice_id == "AFWA-2026-0042"
        ),
        None,
    )
    if final_rule is None:
        raise RuntimeError("Demo final rule proposal was not discovered")
    approved = approve_proposal(
        proposal_path,
        registry_path,
        audit_path,
        final_rule.proposal_id,
        reviewer_note="Approved in reproducible fictional demo",
        now=APPROVAL_TIME,
    )
    reevaluations = reevaluate_affected_employees(
        load_employees(employees_path),
        registry_path,
        audit_path,
        final_rule.proposal_id,
        EVALUATION_DATE,
        now=APPROVAL_TIME,
    )
    reevaluation_path.write_text(
        json.dumps(reevaluations, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    changed_results = [
        item
        for item in reevaluations
        if item["previous_decision"] != item["new_decision"]
        or item["previous_controlling_rule"] != item["new_controlling_rule"]
        or item["previous_hourly_shortfall"] != item["new_hourly_shortfall"]
    ]
    summary: dict[str, object] = {
        "simulation": True,
        "source_id": source.source_id,
        "first_monitoring_state": first.state.value,
        "second_monitoring_state": second.state.value,
        "change_record_path": second.change_record_path,
        "proposal_id": final_rule.proposal_id,
        "proposal_initial_status": final_rule.status.value,
        "approved_rule_id": approved["rule_id"],
        "approved_amount": approved["amount"],
        "approved_effective_date": approved["effective_date"],
        "evaluation_date": EVALUATION_DATE.isoformat(),
        "targeted_employee_count": len(reevaluations),
        "changed_result_count": len(changed_results),
        "audit_path": audit_path.relative_to(output_dir).as_posix(),
        "reevaluation_path": reevaluation_path.relative_to(output_dir).as_posix(),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    """Run the isolated demonstration from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("demo_output"),
        help="New directory for generated demo evidence (default: demo_output)",
    )
    args = parser.parse_args()
    summary = run_demo(args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Operator CLI for regulatory proposal review and approval."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .loader import load_employees
from .monitoring import TRUSTED_SOURCES, SourceConfig
from .workflow import (
    approve_proposal,
    discover_snapshot,
    get_proposal,
    load_proposals,
    reevaluate_affected_employees,
    reject_proposal,
)


def _source(source_id: str) -> SourceConfig:
    for source in TRUSTED_SOURCES:
        if source.source_id == source_id:
            return source
    raise ValueError(f"Unknown trusted source: {source_id}")


def main() -> int:
    """Run one explicit operator workflow command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proposals", type=Path, default=Path("data/proposed_rules.json")
    )
    parser.add_argument(
        "--registry", type=Path, default=Path("data/approved_rules.json")
    )
    parser.add_argument("--audit", type=Path, default=Path("data/audit.jsonl"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover")
    discover.add_argument("source_id")
    discover.add_argument("snapshot", type=Path)
    subparsers.add_parser("list")
    show = subparsers.add_parser("show")
    show.add_argument("proposal_id")
    approve = subparsers.add_parser("approve")
    approve.add_argument("proposal_id")
    approve.add_argument("--note")
    reject = subparsers.add_parser("reject")
    reject.add_argument("proposal_id")
    reject.add_argument("--note")
    reevaluate = subparsers.add_parser("reevaluate")
    reevaluate.add_argument("proposal_id")
    reevaluate.add_argument("--evaluation-date", type=date.fromisoformat, required=True)
    reevaluate.add_argument(
        "--employees",
        type=Path,
        default=Path("data/synthetic_employee_system_of_record.xlsx"),
    )

    args = parser.parse_args()
    if args.command == "discover":
        output = [
            proposal.to_dict()
            for proposal in discover_snapshot(
                _source(args.source_id), args.snapshot, args.proposals, args.audit
            )
        ]
    elif args.command == "list":
        output = [
            {
                "proposal_id": item.proposal_id,
                "notice_id": item.source_notice_id,
                "classification": item.classification.value,
                "status": item.status.value,
            }
            for item in load_proposals(args.proposals)
            if item.status.value == "REVIEW_REQUIRED"
        ]
    elif args.command == "show":
        output = get_proposal(args.proposals, args.proposal_id).to_dict()
    elif args.command == "approve":
        output = approve_proposal(
            args.proposals,
            args.registry,
            args.audit,
            args.proposal_id,
            reviewer_note=args.note,
        )
    elif args.command == "reject":
        output = reject_proposal(
            args.proposals,
            args.audit,
            args.proposal_id,
            reviewer_note=args.note,
        ).to_dict()
    else:
        output = reevaluate_affected_employees(
            load_employees(args.employees),
            args.registry,
            args.audit,
            args.proposal_id,
            args.evaluation_date,
        )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

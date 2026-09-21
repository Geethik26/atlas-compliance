"""Human-reviewed proposal, approval, reevaluation, and audit workflow."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .engine import evaluate_employee
from .models import Employee, MinimumWageRule
from .monitoring import SourceConfig, normalize_visible_text, sha256_content
from .regulatory import (
    ContentClassification,
    ProposalStatus,
    ProposedRule,
    interpret_text,
)
from .rules import load_rules


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def append_audit(
    audit_path: Path,
    event_type: str,
    *,
    timestamp: datetime | None = None,
    **fields: Any,
) -> None:
    """Append one minimized JSON audit event without rewriting history."""
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": (timestamp or utc_now()).astimezone(timezone.utc).isoformat(),
        "event_type": event_type,
        **fields,
    }
    with audit_path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def load_proposals(path: Path) -> list[ProposedRule]:
    """Load proposal records, returning an empty collection if absent."""
    if not path.exists():
        return []
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Proposal store must contain a list")
    return [ProposedRule.from_dict(item) for item in payload]


def save_proposals(path: Path, proposals: list[ProposedRule]) -> None:
    """Replace the proposal index while preserving proposal evidence fields."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps([item.to_dict() for item in proposals], indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def discover_snapshot(
    source: SourceConfig,
    snapshot_path: Path,
    proposal_path: Path,
    audit_path: Path,
    *,
    now: datetime | None = None,
) -> list[ProposedRule]:
    """Interpret a saved raw snapshot and persist only new stable proposals."""
    raw = snapshot_path.read_bytes()
    source_hash = sha256_content(raw)
    text = normalize_visible_text(raw)
    timestamp = now or utc_now()
    interpreted = interpret_text(
        source,
        text,
        snapshot_path=snapshot_path.as_posix(),
        source_hash=source_hash,
        created_at=timestamp,
    )
    append_audit(
        audit_path,
        "SOURCE_INTERPRETED",
        timestamp=timestamp,
        source_id=source.source_id,
        source_snapshot_path=snapshot_path.as_posix(),
        source_hash=source_hash,
        interpreted_count=len(interpreted),
    )
    existing = load_proposals(proposal_path)
    known = {proposal.proposal_id for proposal in existing}
    created = [
        proposal for proposal in interpreted if proposal.proposal_id not in known
    ]
    if created:
        save_proposals(proposal_path, existing + created)
        for proposal in created:
            append_audit(
                audit_path,
                "PROPOSAL_CREATED",
                timestamp=timestamp,
                source_id=proposal.source_id,
                proposal_id=proposal.proposal_id,
                source_notice_id=proposal.source_notice_id,
                classification=proposal.classification.value,
                status=proposal.status.value,
                evidence_reference=proposal.source_snapshot_path,
            )
    return created


def get_proposal(path: Path, proposal_id: str) -> ProposedRule:
    """Return one proposal or raise a clear lookup error."""
    for proposal in load_proposals(path):
        if proposal.proposal_id == proposal_id:
            return proposal
    raise KeyError(f"Unknown proposal: {proposal_id}")


def _load_registry_payload(path: Path) -> list[dict[str, Any]]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise ValueError("Approved rule registry must contain a list of objects")
    return payload


def _save_registry_payload(path: Path, payload: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def approve_proposal(
    proposal_path: Path,
    registry_path: Path,
    audit_path: Path,
    proposal_id: str,
    *,
    reviewer_note: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Explicitly approve one complete final wage proposal, idempotently."""
    timestamp = (now or utc_now()).astimezone(timezone.utc)
    proposals = load_proposals(proposal_path)
    index = next(
        (i for i, item in enumerate(proposals) if item.proposal_id == proposal_id),
        None,
    )
    if index is None:
        raise KeyError(f"Unknown proposal: {proposal_id}")
    proposal = proposals[index]
    registry = _load_registry_payload(registry_path)
    existing = next(
        (item for item in registry if item.get("proposal_id") == proposal_id), None
    )
    if existing is not None:
        return existing
    if proposal.status is ProposalStatus.REJECTED:
        raise ValueError("A rejected proposal cannot be approved")
    if proposal.classification is not ContentClassification.FINAL_RULE:
        raise ValueError("Only a FINAL_RULE wage proposal may be approved")
    required = {
        "source_notice_id": proposal.source_notice_id,
        "jurisdiction": proposal.jurisdiction,
        "amount": proposal.amount,
        "currency": proposal.currency,
        "unit": proposal.unit,
        "effective_date": proposal.effective_date,
        "coverage": proposal.coverage,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            f"Proposal lacks required approval fields: {', '.join(missing)}"
        )
    assert proposal.amount is not None
    assert proposal.effective_date is not None
    prior = [item for item in registry
             if item.get("source_notice_id", item["rule_id"]) == proposal.source_notice_id
             and item["jurisdiction"] == proposal.jurisdiction]
    same_date = [item for item in prior if item["effective_date"] == proposal.effective_date.isoformat()]
    supersedes = same_date[-1]["rule_id"] if same_date else None
    version_id = proposal.source_notice_id if not prior else f"{proposal.source_notice_id}:rev:{proposal.proposal_id.removeprefix('proposal-')}"
    approved: dict[str, Any] = {
        "jurisdiction": proposal.jurisdiction,
        "amount": str(proposal.amount),
        "currency": proposal.currency,
        "unit": proposal.unit,
        "effective_date": proposal.effective_date.isoformat(),
        "rule_id": version_id,
        "source_notice_id": proposal.source_notice_id,
        "supersedes_rule_id": supersedes,
        "publication_date": None if proposal.publication_date is None else proposal.publication_date.isoformat(),
        "coverage": proposal.coverage,
        "proposal_id": proposal.proposal_id,
        "source_id": proposal.source_id,
        "source_url": proposal.source_url,
        "source_snapshot_path": proposal.source_snapshot_path,
        "source_hash": proposal.source_hash,
        "evidence_text": proposal.evidence_text,
        "approved_at": timestamp.isoformat(),
        "reviewer_note": reviewer_note,
    }
    _save_registry_payload(registry_path, registry + [approved])
    proposals[index] = replace(
        proposal,
        status=ProposalStatus.APPROVED,
        reviewed_at=timestamp,
        reviewer_note=reviewer_note,
    )
    save_proposals(proposal_path, proposals)
    append_audit(
        audit_path,
        "PROPOSAL_REVIEWED",
        timestamp=timestamp,
        proposal_id=proposal_id,
        previous_status=proposal.status.value,
        new_status=ProposalStatus.APPROVED.value,
        reviewer_note=reviewer_note,
    )
    append_audit(
        audit_path,
        "RULE_APPROVED",
        timestamp=timestamp,
        source_id=proposal.source_id,
        proposal_id=proposal_id,
        rule_id=version_id,
        source_snapshot_path=proposal.source_snapshot_path,
        source_hash=proposal.source_hash,
        reviewer_note=reviewer_note,
    )
    return approved


def reject_proposal(
    proposal_path: Path,
    audit_path: Path,
    proposal_id: str,
    *,
    reviewer_note: str | None = None,
    now: datetime | None = None,
) -> ProposedRule:
    """Reject a proposal without changing the approved registry."""
    timestamp = (now or utc_now()).astimezone(timezone.utc)
    proposals = load_proposals(proposal_path)
    index = next(
        (i for i, item in enumerate(proposals) if item.proposal_id == proposal_id),
        None,
    )
    if index is None:
        raise KeyError(f"Unknown proposal: {proposal_id}")
    current = proposals[index]
    if current.status is ProposalStatus.APPROVED:
        raise ValueError("An approved proposal cannot be rejected")
    if current.status is ProposalStatus.REJECTED:
        return current
    rejected = replace(
        current,
        status=ProposalStatus.REJECTED,
        reviewed_at=timestamp,
        reviewer_note=reviewer_note,
    )
    proposals[index] = rejected
    save_proposals(proposal_path, proposals)
    append_audit(
        audit_path,
        "PROPOSAL_REVIEWED",
        timestamp=timestamp,
        proposal_id=proposal_id,
        previous_status=current.status.value,
        new_status=ProposalStatus.REJECTED.value,
        reviewer_note=reviewer_note,
    )
    append_audit(
        audit_path,
        "RULE_REJECTED",
        timestamp=timestamp,
        source_id=current.source_id,
        proposal_id=proposal_id,
        reviewer_note=reviewer_note,
    )
    return rejected


def employee_is_affected(employee: Employee, jurisdiction: str) -> bool:
    """Return whether a jurisdictional rule can be a candidate for an employee."""
    if employee.work_country != "Asteria":
        return False
    if jurisdiction == "Asteria Federal":
        return employee.work_state in {"Federal Territory", "Bellwether"}
    if jurisdiction == "Bellwether":
        return employee.work_state == "Bellwether"
    return False


def reevaluate_affected_employees(
    employees: list[Employee],
    registry_path: Path,
    audit_path: Path,
    proposal_id: str,
    evaluation_date: date,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Compare deterministic decisions before and after one approved rule."""
    registry = _load_registry_payload(registry_path)
    trigger = next(
        (item for item in registry if item.get("proposal_id") == proposal_id), None
    )
    if trigger is None:
        raise KeyError(f"No approved rule for proposal: {proposal_id}")
    all_rules = load_rules(registry_path)
    trigger_rule_id = str(trigger["rule_id"])
    previous_rules = [rule for rule in all_rules if rule.rule_id != trigger_rule_id]
    jurisdiction = str(trigger["jurisdiction"])
    results: list[dict[str, Any]] = []
    for employee in employees:
        if not employee_is_affected(employee, jurisdiction):
            continue
        before = evaluate_employee(employee, previous_rules, evaluation_date)
        after = evaluate_employee(employee, all_rules, evaluation_date)
        results.append(
            {
                "employee_id": employee.employee_id,
                "previous_decision": before.decision_state.value,
                "new_decision": after.decision_state.value,
                "previous_controlling_minimum": (
                    None
                    if before.controlling_minimum_wage is None
                    else f"{before.controlling_minimum_wage:.2f}"
                ),
                "new_controlling_minimum": (
                    None
                    if after.controlling_minimum_wage is None
                    else f"{after.controlling_minimum_wage:.2f}"
                ),
                "previous_controlling_rule": before.controlling_rule_version,
                "new_controlling_rule": after.controlling_rule_version,
                "previous_hourly_shortfall": (
                    None
                    if before.hourly_shortfall is None
                    else f"{before.hourly_shortfall:.2f}"
                ),
                "new_hourly_shortfall": (
                    None
                    if after.hourly_shortfall is None
                    else f"{after.hourly_shortfall:.2f}"
                ),
                "evaluation_date": evaluation_date.isoformat(),
                "trigger_proposal_id": proposal_id,
                "trigger_rule_version": trigger_rule_id,
            }
        )
    append_audit(
        audit_path,
        "EMPLOYEES_REEVALUATED",
        timestamp=now,
        proposal_id=proposal_id,
        rule_id=trigger_rule_id,
        evaluation_date=evaluation_date.isoformat(),
        affected_employee_count=len(results),
    )
    return results


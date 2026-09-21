"""Deterministic interpretation of untrusted regulatory source text."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Any

from .monitoring import SourceConfig


class ContentClassification(StrEnum):
    """Supported regulatory-content classifications."""

    FINAL_RULE = "FINAL_RULE"
    PROPOSED_RULE = "PROPOSED_RULE"
    CORRECTION = "CORRECTION"
    INTERPRETIVE_GUIDANCE = "INTERPRETIVE_GUIDANCE"
    INFORMATIONAL = "INFORMATIONAL"
    IRRELEVANT = "IRRELEVANT"
    AMBIGUOUS = "AMBIGUOUS"


class ProposalStatus(StrEnum):
    """Human-review lifecycle states."""

    DISCOVERED = "DISCOVERED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class ProposedRule:
    """Structured interpretation that cannot self-approve."""

    proposal_id: str
    source_id: str
    source_url: str
    source_notice_id: str | None
    classification: ContentClassification
    jurisdiction: str | None
    amount: Decimal | None
    currency: str | None
    unit: str | None
    effective_date: date | None
    publication_date: date | None
    coverage: str | None
    source_snapshot_path: str
    source_hash: str
    evidence_text: str
    interpretation_notes: str
    certainty: str
    status: ProposalStatus
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to stable JSON-compatible values."""
        result = asdict(self)
        result["classification"] = self.classification.value
        result["status"] = self.status.value
        result["amount"] = None if self.amount is None else str(self.amount)
        result["effective_date"] = (
            None if self.effective_date is None else self.effective_date.isoformat()
        )
        result["publication_date"] = (
            None if self.publication_date is None else self.publication_date.isoformat()
        )
        result["created_at"] = self.created_at.isoformat()
        result["reviewed_at"] = (
            None if self.reviewed_at is None else self.reviewed_at.isoformat()
        )
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ProposedRule:
        """Deserialize a stored proposal."""
        return cls(
            proposal_id=str(value["proposal_id"]),
            source_id=str(value["source_id"]),
            source_url=str(value["source_url"]),
            source_notice_id=(
                None
                if value.get("source_notice_id") is None
                else str(value["source_notice_id"])
            ),
            classification=ContentClassification(str(value["classification"])),
            jurisdiction=(
                None
                if value.get("jurisdiction") is None
                else str(value["jurisdiction"])
            ),
            amount=(
                None if value.get("amount") is None else Decimal(str(value["amount"]))
            ),
            currency=None if value.get("currency") is None else str(value["currency"]),
            unit=None if value.get("unit") is None else str(value["unit"]),
            effective_date=(
                None
                if value.get("effective_date") is None
                else date.fromisoformat(str(value["effective_date"]))
            ),
            publication_date=(
                None
                if value.get("publication_date") is None
                else date.fromisoformat(str(value["publication_date"]))
            ),
            coverage=None if value.get("coverage") is None else str(value["coverage"]),
            source_snapshot_path=str(value["source_snapshot_path"]),
            source_hash=str(value["source_hash"]),
            evidence_text=str(value["evidence_text"]),
            interpretation_notes=str(value["interpretation_notes"]),
            certainty=str(value["certainty"]),
            status=ProposalStatus(str(value["status"])),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            reviewed_at=(
                None
                if value.get("reviewed_at") is None
                else datetime.fromisoformat(str(value["reviewed_at"]))
            ),
            reviewer_note=(
                None
                if value.get("reviewer_note") is None
                else str(value["reviewer_note"])
            ),
        )


NOTICE_ID = re.compile(r"\b[A-Z]{3,5}-\d{4}-\d{4}\b")
RATE = re.compile(r"\b(\d+(?:\.\d+)?)\s+([A-Z]{3})\s+(?:per\s+)?(hour|hr)\b", re.I)
MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2}),\s+(\d{4})\b",
    re.I,
)


def _parse_date(match: re.Match[str] | None) -> date | None:
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(0), "%B %d, %Y").date()
    except ValueError:
        return None


def _classify(text: str) -> ContentClassification:
    lower = text.casefold()
    if "proposed rule" in lower or "not effective law" in lower:
        return ContentClassification.PROPOSED_RULE
    if "correction" in lower or "corrected from" in lower:
        return ContentClassification.CORRECTION
    if (
        "interpretive bulletin" in lower
        or "interpretive guidance" in lower
        or "precedence ruling" in lower
    ):
        return ContentClassification.INTERPRETIVE_GUIDANCE
    if "news release" in lower or "informational only" in lower:
        return ContentClassification.INFORMATIONAL
    if "final notice" in lower or "final wage order" in lower:
        return ContentClassification.FINAL_RULE
    if "minimum wage" in lower or "wage rate" in lower:
        return ContentClassification.AMBIGUOUS
    return ContentClassification.IRRELEVANT


def _jurisdiction(source: SourceConfig) -> str | None:
    if source.source_id == "asteria_federal":
        return "Asteria Federal"
    if source.source_id == "bellwether_state":
        return "Bellwether"
    return None


def _notice_blocks(text: str) -> list[tuple[str | None, str]]:
    """Split normalized page text around stable notice IDs."""
    lines = text.splitlines()
    id_lines = [
        index
        for index, line in enumerate(lines)
        if NOTICE_ID.fullmatch(line.strip())
    ]
    if not id_lines:
        inline_ids = list(NOTICE_ID.finditer(text))
        if len(inline_ids) == 1:
            return [(inline_ids[0].group(0), text.strip())]
        return [(None, text.strip())] if text.strip() else []
    blocks: list[tuple[str | None, str]] = []
    for position, line_index in enumerate(id_lines):
        start = max(0, line_index - 2)
        end = id_lines[position + 1] - 2 if position + 1 < len(id_lines) else len(lines)
        notice_id = lines[line_index].strip()
        blocks.append((notice_id, "\n".join(lines[start:end]).strip()))
    return blocks



def _current_rate_card(source: SourceConfig, text: str) -> tuple[str, str] | None:
    """Extract only the authority's own current-rate card, without schedules."""
    start_marker = "Current general rate" if source.source_id == "asteria_federal" else "State minimum wage"
    if start_marker not in text:
        return None
    section = text.split(start_marker, 1)[1]
    end = re.search(r"(?:AFWA|BDL)-MW-[\w.]+", section)
    if not end:
        return None
    card = section[:end.end()]
    rate = RATE.search(card)
    effective = re.search(r"Effective\s+" + MONTH_DATE.pattern, card, re.I)
    if not rate or not effective:
        return None
    # Include the exact card text. Its state/federal comparison is not a notice.
    own_rate = f"{rate.group(1)} {rate.group(2)} per hour"
    evidence = (f"Final notice: current published rate card\n{end.group(0)}\n"
                f"Minimum wage {own_rate} effective {MONTH_DATE.search(effective.group(0)).group(0)}.\n")
    if "covered, nonexempt employees" in card.casefold():
        evidence += "Covered, nonexempt employees\n"
    return end.group(0), evidence


def interpret_text(
    source: SourceConfig,
    text: str,
    *,
    snapshot_path: str,
    source_hash: str,
    created_at: datetime | None = None,
) -> list[ProposedRule]:
    """Classify untrusted text and produce review-required records."""
    timestamp = created_at or datetime.now(timezone.utc)
    timestamp = timestamp.astimezone(timezone.utc)
    proposals: list[ProposedRule] = []
    page_coverage = (
        "Covered, nonexempt employees"
        if "covered, nonexempt employees" in text.casefold()
        else None
    )
    blocks = _notice_blocks(text)
    card = _current_rate_card(source, text)
    if card is not None:
        if all(notice_id is None for notice_id, _ in blocks):
            blocks = []
        blocks.insert(0, card)
    for notice_id, evidence in blocks:
        classification = _classify(evidence)
        rate = RATE.search(evidence)
        effective_match = re.search(
            r"effective\s+" + MONTH_DATE.pattern, evidence, re.I
        )
        # Only an explicitly labeled date or a standalone notice-header date
        # may establish publication. Effective dates never fill this field.
        published_match = re.search(r"(?:publication date|published(?: on)?)\s*:?\s*" + MONTH_DATE.pattern, evidence, re.I)
        header = evidence.split(notice_id, 1)[0] if notice_id else ""
        header_date = next((MONTH_DATE.fullmatch(line.strip()) for line in header.splitlines() if MONTH_DATE.fullmatch(line.strip())), None)
        effective_date = (
            _parse_date(MONTH_DATE.search(effective_match.group(0)))
            if effective_match
            else None
        )
        publication_date = _parse_date(
            MONTH_DATE.search(published_match.group(0)) if published_match else header_date
        )
        amount: Decimal | None = None
        currency: str | None = None
        unit: str | None = None
        if classification is ContentClassification.FINAL_RULE and rate is not None:
            try:
                amount = Decimal(rate.group(1))
            except InvalidOperation:
                amount = None
            currency = rate.group(2).upper()
            unit = "hour"
        coverage = (
            "Covered, nonexempt employees"
            if "covered, nonexempt employees" in evidence.casefold()
            else page_coverage
        )
        coverage_inherited = coverage is not None and (
            "covered, nonexempt employees" not in evidence.casefold()
        )
        required_complete = all(
            (
                notice_id,
                _jurisdiction(source),
                amount,
                currency,
                unit,
                effective_date,
                coverage,
                publication_date,
            )
        )
        certainty = "HIGH" if required_complete else "REVIEW"
        notes = (
            "Deterministic phrase and field extraction; human approval required."
            if required_complete
            else (
                "Content classified, but no complete approvable wage-rate rule "
                "was extracted."
            )
        )
        if coverage_inherited:
            notes += (
                " Coverage was inherited from the explicit page-level "
                "'Covered, nonexempt employees' statement."
            )
        if publication_date is None:
            notes += " Publication date is not stated; do not infer it from the effective date."
        if notice_id and "-MW-" in notice_id:
            notes += " Current-rate card: observed effective date, not an inferred publication date."
        rates = {(m.group(1), m.group(2).upper()) for m in RATE.finditer(evidence)}
        if len(rates) > 1 and classification is ContentClassification.FINAL_RULE:
            amount = None
            certainty = "REVIEW"
            notes += " Multiple wage amounts require manual interpretation."
        identity = json.dumps([source.source_id, notice_id, " ".join(evidence.split()), coverage], ensure_ascii=False)
        proposal_id = "proposal-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        proposals.append(
            ProposedRule(
                proposal_id=proposal_id,
                source_id=source.source_id,
                source_url=source.url,
                source_notice_id=notice_id,
                classification=classification,
                jurisdiction=_jurisdiction(source),
                amount=amount,
                currency=currency,
                unit=unit,
                effective_date=effective_date,
                publication_date=publication_date,
                coverage=coverage,
                source_snapshot_path=snapshot_path,
                source_hash=source_hash,
                evidence_text=evidence,
                interpretation_notes=notes,
                certainty=certainty,
                status=ProposalStatus.REVIEW_REQUIRED,
                created_at=timestamp,
            )
        )
    return proposals


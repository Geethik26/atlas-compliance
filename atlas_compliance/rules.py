"""Approved minimum-wage rule loading."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .models import MinimumWageRule


def load_rules(path: Path) -> list[MinimumWageRule]:
    """Load approved rules from JSON without embedding rates in code."""
    with path.open(encoding="utf-8") as stream:
        payload: Any = json.load(stream)
    if not isinstance(payload, list):
        raise ValueError("Approved rules JSON must contain a list")

    rules: list[MinimumWageRule] = []
    required = {
        "jurisdiction",
        "amount",
        "currency",
        "unit",
        "effective_date",
        "rule_id",
        "coverage",
    }
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError(f"Rule {index} is missing required fields")
        try:
            rule = MinimumWageRule(
                jurisdiction=str(item["jurisdiction"]),
                amount=Decimal(str(item["amount"])),
                currency=str(item["currency"]),
                unit=str(item["unit"]),
                effective_date=date.fromisoformat(str(item["effective_date"])),
                rule_id=str(item["rule_id"]),
                coverage=str(item["coverage"]),
                source_url=(
                    None if item.get("source_url") is None else str(item["source_url"])
                ),
                source_snapshot_path=(
                    None
                    if item.get("source_snapshot_path") is None
                    else str(item["source_snapshot_path"])
                ),
                source_hash=(
                    None if item.get("source_hash") is None else str(item["source_hash"])
                ),
                evidence_text=(
                    None
                    if item.get("evidence_text") is None
                    else str(item["evidence_text"])
                ),
                proposal_id=(
                    None if item.get("proposal_id") is None else str(item["proposal_id"])
                ),
            )
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Rule {index} has invalid data") from exc
        if rule.amount <= 0:
            raise ValueError(f"Rule {index} amount must be positive")
        if not all(
            (
                rule.jurisdiction.strip(),
                rule.currency.strip(),
                rule.unit.strip(),
                rule.rule_id.strip(),
                rule.coverage.strip(),
            )
        ):
            raise ValueError(f"Rule {index} contains an empty required field")
        rules.append(rule)
    return rules

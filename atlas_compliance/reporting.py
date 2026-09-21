"""Privacy-minimized export helpers for compliance evaluation results."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import EvaluationResult


def build_report(results: list[EvaluationResult]) -> dict[str, Any]:
    """Build a deterministic JSON-compatible report and decision summary."""
    counts = Counter(result.decision_state.value for result in results)
    return {
        "record_count": len(results),
        "decision_summary": dict(sorted(counts.items())),
        "results": [result.to_dict() for result in results],
    }


def write_json_report(results: list[EvaluationResult], path: Path) -> None:
    """Write a structured JSON report using only evaluation-result fields."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_report(results), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv_report(results: list[EvaluationResult], path: Path) -> None:
    """Write a flat CSV report, JSON-encoding nested trace fields."""
    rows = [result.to_dict() for result in results]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            flattened = {
                key: (
                    json.dumps(value, sort_keys=True)
                    if isinstance(value, (list, dict))
                    else value
                )
                for key, value in row.items()
            }
            writer.writerow(flattened)

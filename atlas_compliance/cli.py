"""Command-line entry point for deterministic batch evaluation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

from .engine import evaluate_employee
from .loader import load_employees
from .rules import load_rules


def main() -> None:
    """Evaluate a workbook and print results plus decision-state counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--employees", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--evaluation-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    rules = load_rules(args.rules)
    results = [
        evaluate_employee(employee, rules, args.evaluation_date)
        for employee in load_employees(args.employees)
    ]
    for result in results:
        print(json.dumps(result.to_dict(), sort_keys=True))
    counts = Counter(result.decision_state.value for result in results)
    print(json.dumps({"summary": dict(sorted(counts.items()))}, sort_keys=True))


if __name__ == "__main__":
    main()

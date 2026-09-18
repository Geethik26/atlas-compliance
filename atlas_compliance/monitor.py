"""CLI for trusted regulatory source monitoring."""

from __future__ import annotations

import argparse
from pathlib import Path

from .monitoring import TRUSTED_SOURCES, MonitoringState, monitor_source


def main() -> int:
    """Check every configured trusted source and print concise outcomes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path("data"),
        help="Directory containing snapshots and change records (default: data)",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    failed = False
    for source in TRUSTED_SOURCES:
        result = monitor_source(
            source,
            args.evidence_root,
            timeout=args.timeout,
        )
        print(f"{source.name}: {result.state.value}")
        if result.state is MonitoringState.FETCH_FAILED:
            failed = True
            if result.error:
                print(f"  Fetch error: {result.error}")
        elif result.change_record_path:
            print(f"  Change record: {result.change_record_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

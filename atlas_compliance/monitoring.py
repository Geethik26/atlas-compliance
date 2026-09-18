"""Regulatory source snapshots and deterministic change detection.

Fetched source bytes are untrusted evidence. This module stores and compares
them; it never executes or interprets instructions contained in a webpage.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class MonitoringState(StrEnum):
    """Possible outcomes of one source monitoring attempt."""

    FIRST_SNAPSHOT = "FIRST_SNAPSHOT"
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    FETCH_FAILED = "FETCH_FAILED"


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """Allowlisted regulatory source configuration."""

    source_id: str
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class FetchResponse:
    """Raw response returned by a source fetcher."""

    content: bytes
    status: int


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    """Audit metadata for an immutable successful fetch."""

    source_id: str
    source_url: str
    fetched_at: str
    http_status: int
    sha256: str
    snapshot_path: str


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    """Evidence describing a genuine visible-text source change."""

    source_id: str
    previous_hash: str
    new_hash: str
    previous_snapshot_path: str
    new_snapshot_path: str
    detected_at: str
    text_diff: str


@dataclass(frozen=True, slots=True)
class MonitoringResult:
    """Outcome and evidence paths for one monitoring attempt."""

    source: SourceConfig
    state: MonitoringState
    metadata: SnapshotMetadata | None = None
    change_record_path: str | None = None
    error: str | None = None


class Fetcher(Protocol):
    """Callable interface used to isolate network retrieval in tests."""

    def __call__(self, source: SourceConfig, timeout: float) -> FetchResponse:
        """Fetch one configured source."""
        ...


TRUSTED_SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        source_id="asteria_federal",
        name="Asterian Federal Wage Authority",
        url="https://asterian-federal-wage-site.vercel.app/",
    ),
    SourceConfig(
        source_id="bellwether_state",
        name="Bellwether Department of Labor",
        url="https://bellwether-state-wage-site.vercel.app/",
    ),
)


class _VisibleTextParser(HTMLParser):
    """Extract visible text without running scripts or parsing instructions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.parts.append(text)


def sha256_content(content: bytes) -> str:
    """Return the deterministic hexadecimal SHA-256 digest of raw bytes."""
    return hashlib.sha256(content).hexdigest()


def normalize_visible_text(content: bytes) -> str:
    """Extract stable visible text from untrusted HTML bytes."""
    parser = _VisibleTextParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    return "\n".join(parser.parts)


def fetch_source(source: SourceConfig, timeout: float = 15.0) -> FetchResponse:
    """Retrieve raw HTML from a configured source using a bounded timeout."""
    if source not in TRUSTED_SOURCES:
        raise ValueError("Source is not in the trusted source configuration.")
    request = Request(
        source.url,
        headers={"User-Agent": "AtlasComplianceMonitor/0.2"},
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        status = int(response.status)
        content = response.read()
    if not 200 <= status < 300:
        raise RuntimeError(f"Unexpected HTTP status {status}")
    return FetchResponse(content=content, status=status)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _write_unique(directory: Path, stem: str, suffix: str, data: bytes) -> Path:
    """Create a file exclusively, adding a counter rather than overwriting."""
    directory.mkdir(parents=True, exist_ok=True)
    for counter in range(10_000):
        marker = "" if counter == 0 else f"_{counter:04d}"
        path = directory / f"{stem}{marker}{suffix}"
        try:
            with path.open("xb") as stream:
                stream.write(data)
            return path
        except FileExistsError:
            continue
    raise RuntimeError(f"Could not allocate a unique evidence file in {directory}")


def _read_metadata(path: Path) -> SnapshotMetadata | None:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
        return SnapshotMetadata(
            source_id=str(payload["source_id"]),
            source_url=str(payload["source_url"]),
            fetched_at=str(payload["fetched_at"]),
            http_status=int(payload["http_status"]),
            sha256=str(payload["sha256"]),
            snapshot_path=str(payload["snapshot_path"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _successful_metadata(source_dir: Path) -> Iterable[SnapshotMetadata]:
    for path in source_dir.glob("*.metadata.json"):
        metadata = _read_metadata(path)
        if metadata is not None and 200 <= metadata.http_status < 300:
            yield metadata


def _previous_snapshot(
    source: SourceConfig, snapshots_root: Path
) -> tuple[SnapshotMetadata, Path] | None:
    source_dir = snapshots_root / source.source_id
    candidates = sorted(
        (
            item
            for item in _successful_metadata(source_dir)
            if item.source_id == source.source_id and item.source_url == source.url
        ),
        key=lambda item: (item.fetched_at, item.snapshot_path),
    )
    for metadata in reversed(candidates):
        path = snapshots_root.parent / metadata.snapshot_path
        if path.is_file():
            return metadata, path
    return None


def _relative(path: Path, evidence_root: Path) -> str:
    return path.relative_to(evidence_root).as_posix()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def monitor_source(
    source: SourceConfig,
    evidence_root: Path,
    *,
    fetcher: Fetcher = fetch_source,
    timeout: float = 15.0,
    now: Callable[[], datetime] = _utc_now,
) -> MonitoringResult:
    """Fetch, snapshot, and compare one trusted regulatory source."""
    if source not in TRUSTED_SOURCES:
        return MonitoringResult(
            source=source,
            state=MonitoringState.FETCH_FAILED,
            error="Source is not in the trusted source configuration.",
        )
    snapshots_root = evidence_root / "snapshots"
    previous = _previous_snapshot(source, snapshots_root)
    try:
        response = fetcher(source, timeout)
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Unexpected HTTP status {response.status}")
    except (HTTPError, URLError, OSError, RuntimeError, TimeoutError) as exc:
        return MonitoringResult(
            source=source,
            state=MonitoringState.FETCH_FAILED,
            error=f"{type(exc).__name__}: {exc}",
        )

    fetched_at = now().astimezone(timezone.utc)
    timestamp = fetched_at.strftime("%Y%m%dT%H%M%S.%fZ")
    digest = sha256_content(response.content)
    source_dir = snapshots_root / source.source_id
    snapshot_path = _write_unique(source_dir, timestamp, ".html", response.content)
    metadata = SnapshotMetadata(
        source_id=source.source_id,
        source_url=source.url,
        fetched_at=fetched_at.isoformat(),
        http_status=response.status,
        sha256=digest,
        snapshot_path=_relative(snapshot_path, evidence_root),
    )
    _write_unique(
        source_dir,
        snapshot_path.stem,
        ".metadata.json",
        _json_bytes(asdict(metadata)),
    )

    if previous is None:
        return MonitoringResult(
            source=source,
            state=MonitoringState.FIRST_SNAPSHOT,
            metadata=metadata,
        )

    previous_metadata, previous_path = previous
    previous_content = previous_path.read_bytes()
    old_text = normalize_visible_text(previous_content)
    new_text = normalize_visible_text(response.content)
    if old_text == new_text:
        return MonitoringResult(
            source=source,
            state=MonitoringState.UNCHANGED,
            metadata=metadata,
        )

    diff = "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=previous_metadata.snapshot_path,
            tofile=metadata.snapshot_path,
            lineterm="",
        )
    )
    record = ChangeRecord(
        source_id=source.source_id,
        previous_hash=previous_metadata.sha256,
        new_hash=digest,
        previous_snapshot_path=previous_metadata.snapshot_path,
        new_snapshot_path=metadata.snapshot_path,
        detected_at=fetched_at.isoformat(),
        text_diff=diff,
    )
    change_path = _write_unique(
        evidence_root / "changes" / source.source_id,
        timestamp,
        ".change.json",
        _json_bytes(asdict(record)),
    )
    return MonitoringResult(
        source=source,
        state=MonitoringState.CHANGED,
        metadata=metadata,
        change_record_path=_relative(change_path, evidence_root),
    )

"""Offline tests for immutable regulatory source monitoring."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from uuid import uuid4

import pytest

from atlas_compliance.monitoring import (
    FetchResponse,
    MonitoringState,
    SourceConfig,
    TRUSTED_SOURCES,
    fetch_source,
    monitor_source,
    sha256_content,
)

SOURCE = TRUSTED_SOURCES[0]
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
HTML = b"<html><body><h1>Minimum Wage</h1><p>12.82 AST</p></body></html>"


def clock() -> datetime:
    return NOW


@pytest.fixture
def evidence_root() -> Path:
    """Create test evidence without relying on pytest's restricted temp root."""
    path = Path.cwd() / f".monitor-test-{uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def fetch_html(content: bytes, status: int = 200):
    def fetch(source: SourceConfig, timeout: float) -> FetchResponse:
        assert source == SOURCE
        assert timeout > 0
        return FetchResponse(content, status)

    return fetch


def test_first_successful_fetch_creates_first_snapshot(evidence_root: Path) -> None:
    result = monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    assert result.state is MonitoringState.FIRST_SNAPSHOT
    assert result.metadata is not None
    assert (evidence_root / result.metadata.snapshot_path).read_bytes() == HTML
    metadata_files = list(
        (evidence_root / "snapshots/asteria_federal").glob("*.metadata.json")
    )
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["http_status"] == 200
    assert metadata["source_url"] == SOURCE.url


def test_same_html_is_unchanged_and_snapshots_are_not_overwritten(
    evidence_root: Path,
) -> None:
    first = monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    second = monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    assert first.state is MonitoringState.FIRST_SNAPSHOT
    assert second.state is MonitoringState.UNCHANGED
    snapshots = list((evidence_root / "snapshots/asteria_federal").glob("*.html"))
    assert len(snapshots) == 2
    assert len({path.name for path in snapshots}) == 2
    assert all(path.read_bytes() == HTML for path in snapshots)
    assert not (evidence_root / "changes").exists()


def test_modified_visible_html_creates_change_record(evidence_root: Path) -> None:
    changed = b"<html><body><h1>Minimum Wage</h1><p>13.00 AST</p></body></html>"
    monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    result = monitor_source(
        SOURCE, evidence_root, fetcher=fetch_html(changed), now=clock
    )
    assert result.state is MonitoringState.CHANGED
    assert result.change_record_path is not None
    record = json.loads(
        (evidence_root / result.change_record_path).read_text(encoding="utf-8")
    )
    assert record["previous_hash"] == sha256_content(HTML)
    assert record["new_hash"] == sha256_content(changed)
    assert "-12.82 AST" in record["text_diff"]
    assert "+13.00 AST" in record["text_diff"]


def test_sha256_is_deterministic() -> None:
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_content(b"abc") == expected
    assert sha256_content(b"abc") == sha256_content(b"abc")


def test_failed_request_does_not_overwrite_valid_evidence(
    evidence_root: Path,
) -> None:
    valid = monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    assert valid.metadata is not None
    before = {
        path.relative_to(evidence_root): path.read_bytes()
        for path in evidence_root.rglob("*")
        if path.is_file()
    }

    def failed_fetch(source: SourceConfig, timeout: float) -> FetchResponse:
        del source, timeout
        raise URLError("offline")

    failed = monitor_source(SOURCE, evidence_root, fetcher=failed_fetch, now=clock)
    after = {
        path.relative_to(evidence_root): path.read_bytes()
        for path in evidence_root.rglob("*")
        if path.is_file()
    }
    assert failed.state is MonitoringState.FETCH_FAILED
    assert failed.metadata is None
    assert before == after


def test_non_success_http_status_is_fetch_failed(evidence_root: Path) -> None:
    result = monitor_source(
        SOURCE, evidence_root, fetcher=fetch_html(b"unavailable", 503), now=clock
    )
    assert result.state is MonitoringState.FETCH_FAILED
    assert not list(evidence_root.rglob("*.html"))


def test_unconfigured_source_is_never_fetched(evidence_root: Path) -> None:
    called = False

    def forbidden_fetch(source: SourceConfig, timeout: float) -> FetchResponse:
        nonlocal called
        called = True
        return FetchResponse(b"should not be fetched", 200)

    untrusted = SourceConfig("other", "Other", "https://untrusted.example/")
    result = monitor_source(
        untrusted, evidence_root, fetcher=forbidden_fetch, now=clock
    )
    assert result.state is MonitoringState.FETCH_FAILED
    assert called is False


def test_low_level_fetch_rejects_unconfigured_source() -> None:
    untrusted = SourceConfig("other", "Other", "https://untrusted.example/")
    with pytest.raises(ValueError, match="not in the trusted source"):
        fetch_source(untrusted)


def test_markup_only_retry_does_not_create_false_change(
    evidence_root: Path,
) -> None:
    equivalent = b"<html>\n<body><h1> Minimum   Wage </h1><p>12.82 AST</p></body></html>"
    monitor_source(SOURCE, evidence_root, fetcher=fetch_html(HTML), now=clock)
    result = monitor_source(
        SOURCE, evidence_root, fetcher=fetch_html(equivalent), now=clock
    )
    assert result.state is MonitoringState.UNCHANGED
    assert not list(evidence_root.rglob("*.change.json"))

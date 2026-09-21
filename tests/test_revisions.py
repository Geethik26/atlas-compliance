"""Regression coverage for reviewed notice revisions and date provenance."""
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from atlas_compliance.engine import evaluate_employee
from atlas_compliance.loader import load_employees
from atlas_compliance.monitoring import TRUSTED_SOURCES
from atlas_compliance.regulatory import interpret_text
from atlas_compliance.rules import load_rules
from atlas_compliance.workflow import discover_snapshot, approve_proposal

SOURCE = TRUSTED_SOURCES[0]
TEXT = 'Final notice\nAugust 5, 2026\nAFWA-2026-0042\nCovered, nonexempt employees. Minimum wage 13.25 AST per hour effective January 1, 2027.'

def test_publication_is_not_invented_from_effective_date():
    p = interpret_text(SOURCE, TEXT.replace('August 5, 2026\n', ''), snapshot_path='x', source_hash='x')[0]
    assert p.publication_date is None
    assert p.effective_date == date(2027, 1, 1)
    assert p.certainty == 'REVIEW'

def test_header_publication_date_is_preserved():
    p = interpret_text(SOURCE, TEXT, snapshot_path='x', source_hash='x')[0]
    assert p.publication_date == date(2026, 8, 5)

def test_changed_notice_requires_new_review_and_preserves_versions(tmp_path):
    snapshot, proposals, registry, audit = [tmp_path / x for x in ['s.html', 'p.json', 'r.json', 'a.jsonl']]
    registry.write_text('[]')
    snapshot.write_text("".join(f"<p>{line}</p>" for line in TEXT.splitlines()))
    first = discover_snapshot(SOURCE, snapshot, proposals, audit)[0]
    old = approve_proposal(proposals, registry, audit, first.proposal_id)
    assert discover_snapshot(SOURCE, snapshot, proposals, audit) == []
    snapshot.write_text("".join(f"<p>{line}</p>" for line in TEXT.replace('13.25', '14.25').splitlines()))
    revised = discover_snapshot(SOURCE, snapshot, proposals, audit)[0]
    assert revised.proposal_id != first.proposal_id
    assert revised.status.value == 'REVIEW_REQUIRED'
    assert len(load_rules(registry)) == 1
    new = approve_proposal(proposals, registry, audit, revised.proposal_id)
    assert new['supersedes_rule_id'] == old['rule_id']
    assert new['rule_id'] != old['rule_id']
    assert new['publication_date'] == '2026-08-05'
    assert len(load_rules(registry)) == 2
    employee = load_employees(Path('data/synthetic_employee_system_of_record.xlsx'))[0]
    result = evaluate_employee(employee, load_rules(registry), date(2027, 1, 1))
    assert result.controlling_minimum_wage == Decimal('14.25')

def test_evaluation_records_real_run_time_and_allows_fixed_replay_clock():
    employee = load_employees(Path('data/synthetic_employee_system_of_record.xlsx'))[0]
    before = datetime.now(timezone.utc)
    result = evaluate_employee(employee, [], date(2025, 1, 1))
    assert before <= result.evaluation_timestamp <= datetime.now(timezone.utc)
    fixed = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
    assert evaluate_employee(employee, [], date(2025, 1, 1), evaluated_at=fixed).evaluation_timestamp == fixed

def test_live_registry_has_no_unverified_seed_rules():
    assert json.loads(Path('data/approved_rules.json').read_text()) == []

def test_rate_card_extraction_retains_explicit_effective_date():
    text = 'Current general rate\n12.85\nAST per hour\nEffective\nSeptember 21, 2026\nCovered, nonexempt employees\nRule ID\nAFWA-MW-2026.1'
    proposals = interpret_text(SOURCE, text, snapshot_path='x', source_hash='x')
    card = next(p for p in proposals if p.source_notice_id == 'AFWA-MW-2026.1')
    assert card.amount == Decimal('12.85')
    assert card.effective_date == date(2026, 9, 21)
    assert card.publication_date is None
    assert card.status.value == 'REVIEW_REQUIRED'

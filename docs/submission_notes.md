# Atlas Submission Notes

## Submission summary

Atlas is an executable minimum-wage compliance prototype for the fictional
country of Asteria. It implements the complete trusted workflow from regulatory
source monitoring through human-reviewed rule approval and deterministic
employee reevaluation.

The implementation intentionally favors a trustworthy working slice over
production breadth. It does not include a web UI, authentication, cloud
infrastructure, or a production scheduler.

## Time spent

**Total:** 11 hours

## What is simulated

- Asteria, Bellwether, AST currency, agencies, notices, and employees are
  fictional.
- The employee workbook is synthetic and supplied for the exercise.
- The two regulatory websites are assessment sandboxes.
- `demo/fixtures/asteria_before.html` and `asteria_after.html` are tracked,
  fictional replay fixtures derived from the sandbox scenario.
- The demo's reviewer note represents an explicit simulated operator action.
- File-based JSON and JSONL persistence stand in for transactional production
  storage.
- Reevaluation is operator-triggered; production scheduling is not implemented.
- The salary hourly-equivalent calculation is a documented prototype assumption.

No paid AI service or external LLM API is used. Regulatory interpretation is
deterministic and testable. The architecture leaves a boundary where an
AI-assisted extractor could later propose fields, but human approval and
deterministic compliance decisions would remain mandatory.

## Main reviewer commands

Install dependencies in an activated environment:

```powershell
python -m pip install -e ".[dev]"
```

Run the tests:

```powershell
python -m pytest -q -p no:cacheprovider
```

Run the complete isolated replay:

```powershell
python -m atlas_compliance.demo --output demo_output
```

Generate the employee compliance export:

```powershell
python -m atlas_compliance.cli `
  --employees data/synthetic_employee_system_of_record.xlsx `
  --rules data/approved_rules.json `
  --evaluation-date 2026-09-16 `
  --output outputs/compliance_results_2026-09-16.json `
  --format json
```

## Submission contents

- Deterministic compliance engine and decision trace
- Privacy-minimized XLSX loader
- Trusted-source HTTP monitor
- Immutable snapshots and metadata
- Normalized visible-text change detection
- Deterministic notice classification and extraction
- Human approve/reject workflow
- Effective-dated historical rule registry
- Targeted before/after employee reevaluation
- Append-only audit events
- JSON and CSV result exporters
- Tracked simulated replay fixtures
- Regulatory interpretation memo
- Reviewer walkthrough
- Automated tests

## Key assumptions

- Only configured government sandbox URLs are authoritative.
- Covered, active employees are within the prototype scope.
- Federal Territory receives federal rules; Bellwether receives both federal and
  state rules, with the higher rate controlling.
- A rule is eligible when its effective date is on or before the evaluation date.
- Missing historical rules produce `INSUFFICIENT_DATA`.
- Same-date conflicting versions produce `REVIEW_REQUIRED`.
- Equality with the minimum wage is compliant.
- Decisions use unrounded `Decimal` values; displayed money is rounded to cents.

## Known limitations

- Deterministic parsing is tailored to the sandbox's English notice structure.
- Runtime storage is local and assumes a single operator.
- Evidence storage is application-immutable, not hardware-enforced write-once
  storage.
- There is no authentication, reviewer authorization, or dual-control approval.
- There is no production scheduler or stale-source alerting service.
- Retroactive legal changes are documented but not fully replayed across payroll
  periods.
- The prototype does not cover overtime, exemptions beyond the supplied coverage
  flag, deductions, taxes, leave, benefits, or remediation payments.

## Interview discussion prompts

### Prompt injection

Fetched HTML is treated as data. It is never sent to a command interpreter and
cannot call approval functions. Instruction-like phrases remain evidence text.

### Reviewer approval at scale

A production design would add authenticated identities, role-based queues,
four-eyes approval, evidence comparison, bulk review for related jurisdictions,
and service-level monitoring for pending proposals.

### Downtime and missed publications

Atlas preserves the last successful snapshot. Production recovery would alert on
staleness, fetch current content, record the evidence gap, backfill publication
history where possible, and reevaluate affected periods after review.

### Additional jurisdictions and domains

Jurisdiction applicability should move to configured legal-scope relationships.
New compliance domains should have separate deterministic engines and schemas
rather than adding unrelated arithmetic to the minimum-wage engine.

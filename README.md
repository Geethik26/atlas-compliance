# Atlas Compliance — Milestones 1–3

Atlas is a deterministic prototype for evaluating minimum-wage compliance. This
project contains a Python calculation engine, approved rule data, an XLSX loader,
and a regulatory source monitoring and human-reviewed rule lifecycle.

## Privacy boundary

The loader uses an explicit 11-column allowlist. It does not copy or expose
names, national IDs, bank tokens, birth dates, home addresses, personal contact
details, demographic fields, or emergency contacts from the source workbook.

## Decision logic

- Federal Territory employees are evaluated against Asteria Federal rules.
- Bellwether employees are evaluated against both federal and Bellwether rules;
  the higher effective rate controls.
- Only rules effective on or before the evaluation date are candidates.
- Equality is `COMPLIANT`.
- Missing required data or a missing applicable rule produces
  `INSUFFICIENT_DATA`; unsupported or conflicting inputs produce
  `REVIEW_REQUIRED`.
- All monetary calculation uses `Decimal`. Decisions use unrounded values, while
  serialized monetary outputs are rounded to two decimals with half-up rounding.

### Prototype salary assumption

For an `Annual Salary` employee, Atlas derives an hourly equivalent as:

```text
annual_salary_ast / (52 * scheduled_hours_per_week)
```

This is a prototype assumption, not a general legal conclusion. It does not
account for overtime, fluctuating hours, bonuses, deductions, or other facts
that could affect a production compliance analysis.

## Run

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m atlas_compliance.cli `
  --employees data/synthetic_employee_system_of_record.xlsx `
  --rules data/approved_rules.json `
  --evaluation-date 2026-09-16
```

## Regulatory source monitoring

Milestone 2 monitors only these configured trusted sources:

- Asterian Federal Wage Authority:
  `https://asterian-federal-wage-site.vercel.app/`
- Bellwether Department of Labor:
  `https://bellwether-state-wage-site.vercel.app/`

Run both checks from the repository root:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.monitor
```

Each successful fetch stores untouched raw HTML in
`data/snapshots/<source_id>/` and a JSON metadata sidecar containing its UTC
fetch time, HTTP status, SHA-256 hash, source identity, URL, and evidence path.
Files are created exclusively and are never overwritten. A failed fetch does
not write or replace successful evidence.

Atlas compares normalized visible text with the immediately previous successful
snapshot. The result is `FIRST_SNAPSHOT`, `UNCHANGED`, `CHANGED`, or
`FETCH_FAILED`. A genuine visible-text change creates a JSON record under
`data/changes/<source_id>/` containing both raw-content hashes, both snapshot
paths, detection time, and a readable unified diff. Markup-only differences are
not treated as meaningful regulatory change events, though both raw snapshots
and their distinct hashes remain preserved.

All webpage content is treated as untrusted data. Atlas never executes code,
commands, prompts, or instructions found in fetched pages. This milestone only
detects source changes; monitoring itself does not approve or activate rules.

Run the complete offline test suite with:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Proposed rules and human review

Milestone 3 adds a deterministic, testable interpretation boundary. It classifies
saved source text as `FINAL_RULE`, `PROPOSED_RULE`, `CORRECTION`,
`INTERPRETIVE_GUIDANCE`, `INFORMATIONAL`, `IRRELEVANT`, or `AMBIGUOUS` and stores
the source evidence in a structured proposal. Parsing is deliberately narrow:
it recognizes stable notice IDs, explicit wage amounts, dates, and known status
phrases. Missing or uncertain information remains `REVIEW_REQUIRED`.

The lifecycle is:

```text
snapshot -> deterministic interpretation -> REVIEW_REQUIRED proposal
         -> explicit approve/reject -> versioned approved registry
         -> targeted deterministic reevaluation -> append-only audit
```

Regulatory content can only propose a rule. Only the explicit operator `approve`
command can append a complete `FINAL_RULE` to `data/approved_rules.json`.
Proposals, corrections, guidance, news, ambiguous text, and instruction-like
webpage content never self-activate. Reprocessing the same notice and approving
the same proposal are idempotent.

Approved records retain the proposal ID, source ID and URL, snapshot path and
hash, approval timestamp, and reviewer note. Historical rule versions remain in
the registry. For each jurisdiction, the compliance engine selects the latest
version effective on the evaluation date. A future-effective approved rule is
therefore preserved but cannot apply early.

### Targeted reevaluation

A federal wage rule selects employees in Federal Territory and Bellwether because
the federal rule can be a candidate in both. A Bellwether rule selects only
Bellwether employees. Before/after results contain employee ID and compliance
fields only; the calculation itself is still performed exclusively by the
Milestone 1 deterministic engine. Audit events record aggregate affected counts,
not employee PII.

### Operator demonstration

First monitor the trusted sources if snapshots do not already exist:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.monitor --timeout 30
```

Choose a saved snapshot and interpret it. Replace `<snapshot.html>` with an
actual path under `data/snapshots/asteria_federal/` or
`data/snapshots/bellwether_state/`:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.rules_cli discover `
  asteria_federal <snapshot.html>
.venv\Scripts\python.exe -m atlas_compliance.rules_cli list
.venv\Scripts\python.exe -m atlas_compliance.rules_cli show <proposal_id>
```

Explicitly approve or reject after reviewing the evidence:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.rules_cli approve `
  <proposal_id> --note "Reviewed against published final notice"
.venv\Scripts\python.exe -m atlas_compliance.rules_cli reject `
  <proposal_id> --note "Not an active wage rule"
```

After approval, run targeted reevaluation on or after the rule's effective date:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.rules_cli reevaluate `
  <proposal_id> --evaluation-date 2027-01-01
Get-Content data\approved_rules.json
Get-Content data\audit.jsonl
```

Generated proposal indexes, audit logs, reevaluation output, source snapshots,
and change records are ignored by Git. Changes to the approved registry are
intentional operator actions and should be reviewed before committing.

## Architecture and trust boundaries

- `loader.py` reads only the 11 employee fields needed for compliance.
- `monitoring.py` fetches only two allowlisted sources and preserves raw evidence.
- `regulatory.py` deterministically classifies untrusted text into proposals.
- `workflow.py` implements explicit review, versioned approval, targeted
  reevaluation, and append-only audit events.
- `engine.py` alone calculates employee compliance from approved rules.
- `rules_cli.py` exposes the operator workflow; it has no automatic approval path.

The salary conversion remains the prototype assumption documented above:
annual salary divided by `52 * scheduled_hours_per_week`. Atlas is a focused
assessment prototype, not a complete legal interpretation or payroll system.

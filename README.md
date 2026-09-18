# Atlas Compliance — Milestones 1–2

Atlas is a deterministic prototype for evaluating minimum-wage compliance. This
project contains a Python calculation engine, approved rule data, an XLSX loader,
and a regulatory source monitoring layer.

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
detects source changes: it does **not** interpret legal meaning, approve or
activate rules, modify `approved_rules.json`, or re-evaluate employees.

Run the complete offline test suite with:

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

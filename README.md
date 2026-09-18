# Atlas Compliance — Milestone 1

Atlas is a deterministic prototype for evaluating minimum-wage compliance. This
milestone contains only a Python calculation engine, approved rule data, an XLSX
loader, tests, and a batch CLI.

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

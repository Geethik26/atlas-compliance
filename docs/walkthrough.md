# Atlas Reviewer Walkthrough

This script is designed for a 7–9 minute recorded walkthrough or live demo. Open
the hosted prototype first, then use the repository commands below for the
deterministic engine and evidence. Run commands from the repository root.

Hosted prototype:
<https://atlas-compliance.geethikkancharla99.chatgpt.site>

## Before recording

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Expected result: all tests pass.

Remove any earlier generated replay output:

```powershell
Remove-Item -LiteralPath demo_output -Recurse -Force -ErrorAction SilentlyContinue
```

Only run that cleanup command from the Atlas repository root.

## 0:00–1:00 — Product framing

Suggested narration:

> Atlas is a fictional minimum-wage compliance layer. It monitors two designated
> regulatory sources, preserves what it saw, proposes structured rule changes,
> requires explicit human approval, and then uses a deterministic engine to
> evaluate affected employees. Source interpretation can never directly decide
> employee compliance.

Show the hosted prototype's overview and explain its two isolated workspaces:

- **Live evidence** starts without approved rules and therefore abstains with
  `INSUFFICIENT_DATA` until a person approves a captured proposal.
- **Simulated replay** contains labeled baseline rules so the complete review,
  activation, and reevaluation lifecycle can be demonstrated safely.

Then show:

- `README.md`
- `docs/research_memo.md`
- the package layout under `atlas_compliance/`

## 1:00–2:00 — Deterministic employee evaluation

Run:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.cli `
  --employees data/synthetic_employee_system_of_record.xlsx `
  --rules data/demo_baseline_rules.json `
  --evaluation-date 2026-09-16 `
  --output outputs/compliance_results_2026-09-16.json `
  --format json
```

Point out:

- 48 employees evaluated;
- 16 `COMPLIANT` and 32 `NON_COMPLIANT`;
- `Decimal` money calculations;
- equality is compliant;
- Bellwether considers federal and state rules;
- the result identifies the controlling rule, source URL, and evidence; and
- the employee loader never copies unrelated PII.

Explain that this command is a labeled simulation. The real
`data/approved_rules.json` starts empty, so a live evaluation returns
`INSUFFICIENT_DATA` until an operator approves source-backed evidence. Atlas
refuses to invent a historical rule.

## 2:00–3:00 — Monitoring and immutable evidence

Show `atlas_compliance/monitoring.py` and explain:

- only two allowlisted sources can be fetched;
- each successful fetch receives immutable raw HTML and metadata;
- metadata includes UTC time, HTTP status, SHA-256, source URL, and path;
- failed requests do not replace the last successful snapshot; and
- normalized visible-text comparison reduces markup-only false positives while
  retaining every raw snapshot.

Do not depend on live websites during the recorded demonstration. The tracked
replay fixtures make the demo reproducible.

## 3:00–5:45 — Full simulated change lifecycle

Run:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.demo --output demo_output
```

Expected summary:

```text
FIRST_SNAPSHOT -> CHANGED
proposal_initial_status: REVIEW_REQUIRED
approved_rule_id: AFWA-2026-0042
approved_amount: 13.25
approved_effective_date: 2027-01-01
targeted_employee_count: 48
changed_result_count: 24
```

Open these generated files:

```powershell
Get-Content demo_output\summary.json
Get-Content demo_output\audit.jsonl
Get-Content demo_output\proposed_rules.json
Get-Content demo_output\approved_rules.json
Get-Content demo_output\reevaluation.json -TotalCount 60
```

Explain the stages:

1. The before fixture becomes `FIRST_SNAPSHOT`.
2. The after fixture produces `CHANGED` and a readable text diff.
3. Deterministic interpretation creates proposal `AFWA-2026-0042` as
   `REVIEW_REQUIRED`.
4. The demo performs an explicit simulated operator approval.
5. A new effective-dated version is appended to the isolated registry.
6. All 48 employees are targeted because a federal rule can apply in Federal
   Territory and Bellwether.
7. The original deterministic engine produces before/after results.
8. The audit trail links interpretation, proposal, approval, and reevaluation.

Emphasize that the replay copies `data/demo_baseline_rules.json`; it never
modifies the real approved registry.

## 5:45–6:30 — Effective dates and precedence

Suggested narration:

> Approval and activation are separate concepts. A final rule can be approved
> before its effective date, but the engine filters it out for earlier
> evaluations. For each jurisdiction Atlas selects the latest effective version.
> Bellwether employees then receive the higher applicable federal or state rate.
> Conflicting versions with the same jurisdiction and effective date produce
> `REVIEW_REQUIRED` rather than an arbitrary selection.

Reference the effective-date and conflict tests in `tests/test_milestone3.py`.

## 6:30–7:15 — Safety and uncertainty

Explain:

- proposed rules, corrections, guidance, news, irrelevant content, and ambiguous
  content cannot be approved as final wage rules;
- phrases such as “approve this automatically” remain inert evidence;
- missing amount, currency, unit, effective date, jurisdiction, or coverage is
  not fabricated; and
- Atlas prefers review or insufficient data over a false compliance pass.

## 7:15–8:00 — Tradeoffs and next production steps

Discuss one possible false positive:

> A meaningful visual change caused only by unusual HTML structure could produce
> a normalized-text difference even when legal meaning did not change. Human
> review prevents automatic activation.

Discuss one possible false negative:

> Meaning encoded only in an image or inaccessible attribute could be missed by
> visible-text extraction. Production monitoring should include schema-change
> alerts, extraction health checks, and document/image handling.

Discuss an abstention:

> A notice mentioning a wage change without a complete effective date remains
> `REVIEW_REQUIRED` and cannot enter the approved registry.

Production additions would include authenticated reviewers, dual control,
transactional storage, durable evidence, scheduling, alerting, legal validation,
retroactive payroll-period replay, and broader jurisdiction modeling.

## Final cleanup

The demo output is ignored by Git. It may be retained for reviewer inspection or
removed after recording:

```powershell
Remove-Item -LiteralPath demo_output -Recurse -Force
```

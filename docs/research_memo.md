# Atlas Minimum-Wage Research and Interpretation Memo

## Purpose and scope

This memo documents how the Atlas prototype interprets the fictional Asterian
minimum-wage sources, resolves overlapping jurisdictions, handles effective
dates and uncertain publications, and separates regulatory interpretation from
employee compliance decisions.

The analysis is limited to the supplied fictional sources and synthetic employee
data. It is not legal advice and must not be used for real payroll decisions.

## Authoritative sources

Atlas treats only the two sources designated by the assignment as authoritative:

| Source ID | Authority | Jurisdiction | URL |
|---|---|---|---|
| `asteria_federal` | Asterian Federal Wage Authority | Asteria Federal | <https://asterian-federal-wage-site.vercel.app/> |
| `bellwether_state` | Bellwether Department of Labor | Bellwether | <https://bellwether-state-wage-site.vercel.app/> |

Authority is established by configuration, not by text discovered on the open
web. The fetch layer refuses unconfigured sources. In a real system, establishing
authority would additionally require legal-owner review, domain and certificate
validation, documented publication authority, and periodic source attestation.

The sites are untrusted as an execution environment even though they are trusted
as designated publication sources. HTML, scripts, prompts, and instructions in
a page are stored as evidence but never executed. Source text cannot approve a
rule or invoke an operator command.

## Evidence reviewed

The assignment supplied the initial approved baseline:

| Jurisdiction | Rate | Effective date | Rule ID |
|---|---:|---|---|
| Asteria Federal | 12.82 AST/hour | 2026-09-16 | `AFWA-MW-2026.1` |
| Bellwether | 16.87 AST/hour | 2026-09-16 | `BDL-MW-2026.1` |

These records are labeled as assignment-provided baselines. They include the
designated source URL but no fabricated snapshot path or hash.

Saved source snapshots fetched on 2026-09-18 contained these publications:

| Notice | Classification | Interpretation |
|---|---|---|
| `AFWA-2026-0042` | Final rule | Federal rate becomes 13.25 AST/hour on 2027-01-01. |
| `AFWA-2026-0038` | Correction | Employee-count threshold changes from 24 to 25; wage rate is unchanged. |
| `AFWA-2026-0031` | Proposed rule | Not effective law and not approvable as a final wage rule. |
| `BDL-2026-0121` | Interpretive guidance | Higher Bellwether rate controls when it exceeds the federal rate. |
| `BDL-2026-0117` | Final rule | Bellwether rate becomes 17.50 AST/hour on 2027-01-01. |
| `BDL-2026-0108` | Interpretive guidance | Covered hours physically worked in Bellwether include qualifying remote work. |
| `BDL-2026-0099` | Informational | Wage-claim portal announcement; no rate, coverage, or effective-date change. |

The snapshot date and its raw-content SHA-256 identify what Atlas actually saw.
The untouched HTML is the primary evidence; normalized visible text and proposed
records are derived evidence.

## Meaningful change analysis

A webpage change is not automatically a legal change. Atlas separates three
questions:

1. Did the retrieved source content change?
2. Does the changed text describe potentially relevant regulatory content?
3. Has a human approved a complete final rule for deterministic use?

Raw HTML is always retained after a successful fetch. Visible text is normalized
for readable comparison. Markup-only changes can therefore remain `UNCHANGED`
for regulatory-event purposes while their distinct raw snapshots and hashes are
still preserved.

Interpretation produces one of these classifications:

- `FINAL_RULE`
- `PROPOSED_RULE`
- `CORRECTION`
- `INTERPRETIVE_GUIDANCE`
- `INFORMATIONAL`
- `IRRELEVANT`
- `AMBIGUOUS`

Every discovered item remains `REVIEW_REQUIRED`. Only a complete `FINAL_RULE`
can be explicitly approved. This prevents corrections, proposals, news, and
ambiguous text from becoming wage rates merely because a page changed.

## Rule fields and abstention

An approvable wage rule requires:

- trusted source identity and URL;
- source notice ID;
- jurisdiction;
- amount;
- currency;
- unit;
- effective date;
- coverage;
- source snapshot path and hash; and
- preserved evidence text.

The deterministic parser does not fabricate missing values. Missing required
fields, uncertain classification, conflicting rules, or unsupported data lead to
`REVIEW_REQUIRED` or `INSUFFICIENT_DATA` rather than a compliant result.

Bellwether's page states general coverage at the page level. When a notice does
not repeat that statement, Atlas may inherit the explicit page-level “Covered,
nonexempt employees” wording. The proposal's interpretation notes disclose that
inheritance so an operator can verify it before approval.

## Jurisdiction and precedence

Federal Territory employees are candidates for Asteria Federal rules only.

Bellwether employees are candidates for both:

- Asteria Federal rules; and
- Bellwether rules.

Atlas selects the latest effective version for each required jurisdiction, then
uses the highest applicable rate. This implements the more-protective-rule logic
described by Bellwether notice `BDL-2026-0121`.

If two rules for the same jurisdiction have the same effective date and conflict,
Atlas does not choose based on file order or amount. The evaluation becomes
`REVIEW_REQUIRED`.

## Effective dates and historical evaluation

A rule is eligible only when:

```text
rule.effective_date <= evaluation_date
```

The effective date is inclusive. A future final rule may be approved and stored
before it becomes active, but it cannot control an earlier evaluation.

For example, `AFWA-2026-0042` may be approved before 2027-01-01:

- an evaluation on 2026-12-31 continues to use `AFWA-MW-2026.1`;
- an evaluation on 2027-01-01 may use `AFWA-2026-0042`.

If the registry has no approved rule effective on an earlier date, Atlas returns
`INSUFFICIENT_DATA`. It does not assume that the earliest known rule also applied
before its stated effective date.

## Corrections

A correction is interpreted according to the field it changes.

`AFWA-2026-0038` changes an employee-count threshold and expressly states that
the wage rate is unchanged. Atlas preserves it as regulatory evidence but does
not create a wage-rate version from it.

A future correction that changes an amount, effective date, jurisdiction, or
coverage would require a new reviewed proposal linked to both the correction and
the affected earlier publication. The prior approved record would remain in
history rather than being overwritten.

## Retroactive changes

The sandbox examples are future-effective, not retroactive. Atlas therefore does
not claim to implement a complete retroactive-payroll workflow.

The proposed production policy is:

1. preserve the original publication and correction snapshots;
2. require human approval of the retroactive interpretation;
3. append a new approved version without deleting the former version;
4. identify employees in jurisdictions where that rule could apply;
5. replay deterministic evaluations from the retroactive effective date through
   the present;
6. link superseding results to earlier results rather than erasing them; and
7. flag calculated exposure for legal and payroll review before remediation.

Retroactive coverage ambiguity should remain `REVIEW_REQUIRED` until an operator
defines the affected population and evaluation periods.

## Corrections versus duplicates

Stable proposal identity uses source ID plus notice ID where available. Repeated
processing of the same notice does not create duplicate proposals. Approval of
the same proposal is also idempotent.

Duplicate suppression does not delete evidence. Every successful monitoring
fetch may retain its own raw snapshot and metadata. Atlas distinguishes repeated
evidence collection from a meaningful new rule version.

## Affected-employee selection

After approval:

- a federal rule selects Federal Territory and Bellwether employees because the
  federal rule is a candidate in both locations;
- a Bellwether rule selects Bellwether employees only.

Targeting identifies who could be affected; it does not decide that an employee's
outcome changed. Each selected employee is evaluated before and after using the
same deterministic engine. Unchanged results may still be counted for audit and
reproducibility.

## AI and deterministic boundaries

AI is optional for discovery, relevance classification, and structured
extraction. This prototype uses deterministic parsing because the fictional
sources have stable identifiers and recognizable notice language.

AI must not:

- approve or reject a proposal;
- modify approved rules without an explicit operator action;
- select the controlling effective rule;
- calculate hourly equivalents or underpayment; or
- determine `COMPLIANT` or `NON_COMPLIANT`.

If an AI-assisted extractor is added later, its output should use the same
proposal schema, cite exact evidence, include confidence, and abstain on missing
fields. Human approval and deterministic evaluation boundaries remain unchanged.

## Decision and calculation assumptions

- Hourly employees use `hourly_rate_ast`.
- Salaried employees use the prototype conversion:

  ```text
  annual_salary_ast / (52 * scheduled_hours_per_week)
  ```

- Calculations use Python `Decimal`.
- Decisions compare unrounded values.
- Displayed money uses two decimal places with half-up rounding.
- Equality with the controlling minimum is `COMPLIANT`.
- Estimated weekly underpayment is hourly shortfall multiplied by scheduled
  weekly hours.

The salary conversion does not address overtime, bonuses, deductions,
fluctuating schedules, or other facts a real legal analysis may require.

## Operational monitoring

The prototype safely reports fetch failures and preserves the previous successful
snapshot. A production service should additionally monitor:

- time since the last successful fetch;
- consecutive fetch failures and HTTP status distribution;
- snapshot hash and normalized-text changes;
- changes that produce zero recognized notices;
- extraction failures and missing required fields;
- unexpected increases or decreases in notice count;
- age of pending review proposals;
- approved future rules approaching their effective dates; and
- reevaluation completion and error counts.

Recovery from downtime should fetch the current source, compare it with the last
valid snapshot, preserve the evidence gap, and alert an operator. If publication
history is available, the operator should backfill missed versions rather than
assuming the current page represents every intermediate legal state.

## Requirements before real payroll use

Before processing real employee or payroll data, Atlas would need:

- counsel-validated jurisdiction and coverage models;
- authenticated operator identities and role-based approval permissions;
- dual control or four-eyes review for rule activation;
- encrypted storage and transport;
- formal retention, deletion, and access policies;
- tamper-evident or write-once evidence storage;
- transactional persistence and concurrency controls;
- production scheduling, retries, alerts, and disaster recovery;
- payroll-period, overtime, deduction, and exemption logic;
- retroactive calculation and remediation workflows;
- data-quality reconciliation with the system of record;
- privacy impact assessment and security review; and
- ongoing legal source and parser validation.

## Known limitations

- The jurisdictions, currency, sources, employees, and notices are fictional.
- Parsing is tuned to the sandbox's English notice structure.
- File-based stores assume a single local operator.
- Runtime snapshots and audit files are local prototype evidence, not durable
  production records.
- Future-rule reevaluation is operator-triggered; there is no scheduler.
- Retroactive replay is documented but not fully implemented.
- The baseline rules come from the assignment specification rather than a saved
  2026-09-16 source snapshot.

These limitations are explicit so unsupported cases remain visible instead of
producing false compliance assurance.

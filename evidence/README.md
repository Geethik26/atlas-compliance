# Submission verification and audit evidence

This package was generated from source commit
`fcab9dd9476db4ec1da011d71657206be7c8257c`. The existing automated tests passed
locally: **55 passed**. See [the test run record](test_results.txt) for the command,
environment, and captured output.

## Reproduce the checks

From the repository root, in a Python 3.11+ environment with the dependencies
installed:

```sh
python -m pytest -q -p no:cacheprovider
python -m atlas_compliance.demo --output demo_output
```

The demo requires a new output directory. Use another new directory if
`demo_output` already exists. Do not overwrite this committed evidence package.

## Inspect the change event

All files below are from one execution of:

```sh
python -m atlas_compliance.demo --output evidence/change_replay
```

| Evidence | What it demonstrates |
| --- | --- |
| [Summary](change_replay/summary.json) | FIRST_SNAPSHOT to CHANGED; 48 targeted employees and 24 changed results |
| [Before snapshot](change_replay/snapshots/asteria_federal/20261215T120000.000000Z.html) | Preserved first source version |
| [After snapshot](change_replay/snapshots/asteria_federal/20261215T120500.000000Z.html) | Preserved changed source version |
| [Before metadata](change_replay/snapshots/asteria_federal/20261215T120000.000000Z.metadata.json) / [after metadata](change_replay/snapshots/asteria_federal/20261215T120500.000000Z.metadata.json) | Source URL, simulated fetch time, and raw-content SHA-256 |
| [Change record](change_replay/changes/asteria_federal/20261215T120500.000000Z.change.json) | Linked snapshots, hashes, and readable text diff |
| [Proposal](change_replay/proposed_rules.json) | Extracted rule, evidence, and recorded review outcome |
| [Approved registry](change_replay/approved_rules.json) | Preserved baseline rules plus approved AFWA-2026-0042, 13.25 AST/hour effective 2027-01-01 |
| [Audit trail](change_replay/audit.jsonl) | Interpretation, proposal creation, explicit simulated approval, rule append, and reevaluation |
| [Employee reevaluation](change_replay/reevaluation.json) | Before/after decisions and shortfalls for the 48 supplied synthetic employees |

## Simulation and scope

The replay uses the tracked fictional HTML fixtures, an injected local fetcher,
fixed simulated December 2026 event times, and a January 2027 evaluation date.
These are scenario timestamps, not claims of a live fetch or real operator review
on those dates. The approval is an explicitly simulated operator action performed
by the demo. Running it requires no network and leaves `data/approved_rules.json`
unchanged.

The package demonstrates the federal change workflow; the source monitor is
configured for both assessment sites. It does not establish current live-source
availability or repair the documented baseline evidence limitations. Baseline
source snapshot paths and hashes remain null in the copied registry.

Snapshot paths in snapshot metadata and the change record are relative to
`evidence/change_replay/`. Proposal and approved-rule snapshot paths are relative
to the repository root because that was the demo's working directory.

Passing tests document the existing suite's result, not exhaustive correctness
or production readiness. The implementation's existing limitations remain as
documented in the research memo and submission notes.

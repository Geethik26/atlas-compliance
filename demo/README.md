# Reproducible Atlas Change Replay

The fixtures in this directory demonstrate the assignment workflow without
depending on a live website change.

- `fixtures/asteria_before.html` contains the approved federal baseline.
- `fixtures/asteria_after.html` adds final notice `AFWA-2026-0042` for a future
  13.25 AST/hour rate effective 2027-01-01.

Run:

```powershell
.venv\Scripts\python.exe -m atlas_compliance.demo --output demo_output
```

The command creates an isolated evidence package containing:

```text
demo_output/
  snapshots/
  changes/
  proposed_rules.json
  approved_rules.json
  audit.jsonl
  reevaluation.json
  summary.json
```

The command refuses to overwrite an existing output directory. The output is
ignored by Git and the real `data/approved_rules.json` is copied, never modified.


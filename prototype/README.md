# Hosted prototype source

This directory mirrors the assessment-specific code deployed at
<https://atlas-compliance.geethikkancharla99.chatgpt.site>.

The UI executes the same deterministic Python engine in a self-hosted Pyodide
runtime. `/api/session` stores append-only anonymous session revisions in D1,
and `/api/sources` is restricted to the two configured assessment URLs. Live
and simulated workspaces are isolated. Only an explicit reviewed action can add
an approved rule and trigger reevaluation.

The deployment also contains the standard Sites/Vinext build scaffold and the
official Pyodide 0.27.7 distribution. Generated starter files, dependencies,
build output, and the 14 MB third-party Pyodide binaries are intentionally not
duplicated in this repository. The authored application, API routes, migration,
bootstrap data, and browser engine adapter are preserved here for review.

The production source commit is `87818ca1a9ffb6f78500c756ac542518364435b3`.

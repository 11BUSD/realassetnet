---
name: ran-vertical-slice
description: Verify the Realassetnet synthetic broker-to-investor workflow and produce release evidence for a changed candidate.
---

Read `docs/demo-script.md` and `docs/production-blockers.md`. Use a disposable simulation database within project `runtime/` and synthetic identities. Do not change or reset an existing user's database. Start the local server with an explicit disposable database environment if UI verification is needed.

Verify the affected sequence: intake, safe extraction, user confirmation, immutable snapshot, independent review, factual publication, separate room/eligibility grants, simulated participation, investor holdings, distribution and audit integrity. Include denial checks for another broker tenant, unauthorized investor room access, self-approval and disabled live actions. On ledger changes verify cent conservation, capacity and idempotency with changed-payload rejection.

Compare public API responses with private room responses; visual hiding is not sufficient. Test at least one stale/missing/conflicting-evidence block when evidence or underwriting changes. Confirm source claims and historical snapshots remain unchanged after later actions.

Run `python scripts/release_check.py` for final test and source-hash evidence. Report what was observed, the exact candidate evidence path and unresolved limits. The script does not deploy or merge; do not interpret a passing gate as production or financial authorization. Avoid installing new tools or creating recurring agent tasks unless the user's scope calls for them.

---
name: ran-invariant-review
description: Review Realassetnet domain, policy, schema, or disclosure changes against the property/deal and evidence-control invariants.
---

Read `docs/invariants.md` and the changed domain/gateway/schema code in the project root two levels above this skill. Review actual server behavior, not labels or hidden buttons. Trace actor to organization, resource permission, room permission, policy decision, mutation and audit.

Look for property/security conflation; public leakage of room materials; unknown converted to clear/none; overwritten conflicting claims; historical underwriting rewrite; agent output treated as authority; same-role cross-tenant access; direct sensitive-action mutation; startup rights bundled into property participation; and simulation states relabelled as legally effective states.

For each actionable finding give the concrete trigger, affected resource boundary, consequence, code location and a meaningful failing test. If the code safely defers a capability, document that limit instead of demanding its speculative implementation. Keep recommendations within the user's requested change. Do not request a new approval for routine review or reversible fixes already authorized.

Use synthetic fixtures only. Never inspect or copy the parent workspace's private counterparty data for a public release. Run relevant regression tests and `python scripts/scan_public.py` after a fix. A passing scanner is not proof of confidentiality; inspect the exact publication diff. Report unresolved release blockers plainly without deploying or merging.

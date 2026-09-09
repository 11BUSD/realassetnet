# Software factory and high-value next steps

The factory turns a narrowly stated outcome into a reviewable change, invariant tests, source hashes and a release decision. Its implemented parts are a machine-readable stage manifest, three project-local skills, deterministic tests, a publication scanner, a local release-evidence command and CI configuration. It does not autonomously launch agents, select paid models, merge code or deploy.

Use a bounded work packet: outcome, owned files, domain invariants, source/fixture provenance, permitted side effects, acceptance checks and production impact. Implementation can proceed in parallel only when the user or applicable instructions authorize delegation and file ownership is clear. Integration belongs to a single responsible reviewer. The release gate records exact file hashes so the approval can refer to the candidate actually tested.

## Prioritized experiments

These are proposed product experiments, not implemented features or valuation promises. The durable value comes from lower verification cost, higher completion rates, trustworthy data rights and repeatable transaction connectivity. Measure those outcomes before marketing a moat.

| Priority | Experiment | User/business benefit | Concrete acceptance measure | Guardrail |
|---|---|---|---|---|
| 1 | Evidence-change impact map | Show exactly which NOI, debt assumptions, claims and decisions become stale when a document changes | Every changed claim identifies all affected snapshots and pending approvals; zero silent rewrites | Preserve originals; human decides which revision supersedes which |
| 1 | Stale-evidence repricing workbench | Give originators a short queue of evidence refreshes with transparent scenario deltas | Median refresh-to-reviewed-snapshot time and unresolved stale-claim count | Scenario delta is an estimate, never an automatic lender quote or appraisal |
| 1 | Encumbrance claim collision inbox | Surface mortgage/security/pending-capital overlap before a new transaction advances | All potentially overlapping claims have sources, responsible reviewer and disposition reason | Do not calculate legal priority or label an asset unencumbered |
| 1 | Historical policy replay sandbox | Explain why a previously permitted action would change under a candidate pack | Replays on frozen synthetic cases return explicit old/new decisions with source policy hashes | No mutation or live execution during replay |
| 2 | Private counterparty adapter | Use the researched institutional graph without leaking it into public software | Tenant/purpose-filtered matches retain every mandate source and freshness flag | Read-only by default; invitations still require authorized gateway execution |
| 2 | Evidence-request optimizer | Ask for the smallest set of documents that resolves the largest number of blocking decisions | Measured reduction in duplicate requests and review cycles | Explicit missing facts; never generate substitute evidence |
| 2 | Reusable permissioned transaction passport | Reuse approved factual evidence across financing, sale and diligence workflows | Reduced re-entry with independent deal permissions and traceable source reuse | Consent, expiry and purpose attach to disclosure, not merely to property ID |
| 3 | Provider readiness adapters | Route appraisal, survey, legal and administration demand based on demonstrated capability | Completed provider sandbox workflows, response quality and turnaround | Provider listings are not partnership or licensing verification |
| 3 | Incident rehearsal factory | Generate synthetic cross-tenant, stale-policy and hostile-document cases for each release | A known-bad candidate reliably fails without exposing real data | No live malware or uncontrolled external tools |

Start with the first four experiments after the V0 acceptance checks pass. They improve evidence integrity and review speed without prematurely adding financial execution. The private adapter then connects the existing relationship-research work at a clear data boundary. Tokenization is a later instrument/registry integration choice, not a shortcut around legal rights or a substitute for settlement controls.

## Factory work-packet example

```json
{
  "objective": "Invalidate publication proposals when a referenced claim becomes stale",
  "scope": "domain policy and synthetic regression fixtures",
  "invariants": ["immutable historical snapshot", "unknown remains unknown", "human material-release approval"],
  "acceptance": ["fresh evidence can proceed", "stale evidence blocks", "old snapshot unchanged", "audit records reason"],
  "external_actions": [],
  "release": "reviewed source hash only; no automatic deploy"
}
```

# Data dictionary

The migration is the authoritative schema. IDs are opaque text identifiers; timestamps are UTC ISO strings except session expiry epoch seconds. JSON columns hold deterministic envelopes or versioned inputs, not arbitrary executable expressions. Simulated ledger monetary amounts are integer cents; fees use basis points. Property/intake and underwriting values use validated finite numbers and are not the settlement ledger.

| Tables | Purpose and trust |
|---|---|
| organizations, users, sessions | Synthetic tenant ownership, identity, role, salted password hash, hashed session token, CSRF secret and expiry |
| properties | Physical asset identity and reviewed public marketing state; never the security |
| artifacts | Original accepted text, SHA-256, contributor, filename, version, quarantine/parse status |
| claims | Separate field assertions, category, original source reference, version; multiple conflicting assertions remain |
| claim_confirmations | Explicit user acknowledgement; does not independently authenticate the source |
| claim_reconciliations | Append-only independent-review selection of a confirmed numeric claim with considered claim IDs and reason; new claims invalidate the decision |
| professional_opinions | Separate authored professional assertion and claimed credentials; not credential verification |
| model_estimates | Versioned calculated estimate, inputs, category; not appraisal or NAV |
| underwriting_snapshots | Frozen inputs, evidence IDs, formula/assumptions/scenarios/results and review state |
| derived_metrics | Numeric or structured results tied to a particular snapshot and formula |
| evidence_requests | Missing-evidence workflow records with field/reason/actor |
| asset_claims | Ownership, lien, mortgage, debt, security, encumbrance, pending-capital and restriction assertions requiring review |
| legal_entities | Distinct synthetic SPVs with PROPERTY_ONLY scope |
| deals, capital_requirements | Specific proposed transaction and amount/purpose/currency, separate from its property |
| instruments, offerings | Synthetic participation instrument and offer conditions; transfer disabled |
| eligibility, room_grants | Separate simulated investor review and property-specific disclosure permission |
| holdings, transactions, distributions | Simulated participation positions, idempotent event ledger and cent-exact distributions |
| action_proposals | Sensitive requested action, actor, payload, policy version, decision and reason |
| agent_runs | Versioned agent output envelope with source references and limitations |
| audit_events | Append-only sequence, actor, resource, event, structured details and hash-chain linkage |
| schema_versions | Applied migration record |

SOURCE_PROVIDED is the stored source-claim category. USER_CONFIRMED is derived from confirmation records. UNVERIFIED, STALE and CONFLICTING describe current evidentiary status. REALASSETNET_CALCULATED and REALASSETNET_ESTIMATE describe calculation provenance, not third-party endorsement. Professional opinions remain separate objects. UNKNOWN is an explicit knowledge limit; a missing row never clears ownership, liens, condition, environmental risk or eligibility.

The asset graph currently links claim rows to a property and optional evidence claim. Possible overlap is conservatively signalled when multiple claims exist. It is not a full registry-backed title graph, interest-priority engine, beneficial-ownership resolver or automatic enforcement mechanism.

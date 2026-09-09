# Domain and control invariants

| Requirement | V0 representation | Important limit |
|---|---|---|
| Property is not a security | Separate property, deal, capital requirement, legal entity, instrument, offering, holding, transaction tables | One simulated deal per property is executable today |
| Discovery is not offering access | Public projection and separately authorized room | Registration and eligibility alone do not open a room |
| Evidence is not a claim | Immutable artifacts/claims; separate confirmations, opinions, estimates, metrics | Professional reports are not externally verified |
| Unknown is not none | Ownership and encumbrance clearance stay UNKNOWN; legal priority NOT_DETERMINED | Empty claim collection cannot mean clear title |
| Preserve conflict | Numeric conflict blocks until independent append-only reconciliation; asset claims flag possible overlap | New claims reopen reconciliation; legal-priority selection is prohibited |
| Version underwriting | Immutable snapshots with input IDs, formulas, scenarios, creator, timestamp | Later evidence requires a new snapshot; no silent historical rewrite |
| Compose packs | Toronto market separate from Ontario/Canada simulation jurisdiction packs | No validated production rules or extra markets |
| Gate sensitive actions | Gateway allowlist and policy decisions | No live payments, issuance, transfer, referral or invitations |
| Agents propose | Structured deterministic envelopes; domain execution | Some catalog agents are contract-only; no LLM connected |
| Tenant isolation | Organization ownership plus explicit room grants | Admin is a trusted cross-organization reviewer |
| State machines | Server-selected property and simulation states | No generic frontend status setter; full live lifecycle deferred |
| Separate public/private | Project-only publication allowlist and synthetic demo | Pattern scanner complements, never replaces, human diff review |

The intended disclosure vocabulary is LEVEL_0_PUBLIC, LEVEL_1_REGISTERED, LEVEL_2_QUALIFIED, LEVEL_3_APPROVED_DATA_ROOM and LEVEL_4_TRANSACTION_PARTICIPANT. V0 enforces public projection, authenticated session, independent simulated eligibility, explicit level-3 room grant and a level-4 participation upgrade. These are distinct permissions; the numeric levels are not a blanket inheritance rule for arbitrary documents.

The property executor moves DRAFT to IN_REVIEW to PUBLISHED. Artifacts are PARSED or QUARANTINED after intake; content remains immutable. Eligibility is APPROVED_SIMULATION only after reviewer action. Offerings, participation and settlement retain explicit simulation labels. Do not rename these to live or legally approved states.

Never add a generic endpoint that writes a requested status, accepts the caller's organization as authority, changes a claim in place, assigns professional certainty to a model estimate, or treats an uploaded instruction as a command. New executors require policy, authorization, evidence and audit tests before being wired into the API.

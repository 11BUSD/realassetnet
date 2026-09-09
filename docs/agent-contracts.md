# Agent contracts

The application catalog is versioned in `app/packs.py`. These are bounded deterministic functions and future adapter contracts, not ten autonomous deployed LLM workers. Only actual `agent_runs` are execution evidence. Catalog presence does not mean that every agent has an independent queue, scheduling, retries or a model endpoint.

Every emitted envelope contains agent identity, model/version, input references, source references, structured output, confidence, assumptions, missing information, contradictions, proposed actions and timestamp. Confidence identifies rule-execution confidence, not factual accuracy or investment probability. Source evidence is never replaced with generated output.

| Agent | Implemented responsibility or boundary |
|---|---|
| Intake | Validate synthetic GTA asset intake and record missing ownership/encumbrance evidence |
| Document parser | Extract allowlisted numeric claims from text/CSV; emit security findings |
| Evidence | Detect required, stale and unconfirmed claims through domain checks |
| Rent/comps | Contract only; no market data feed |
| Underwriting | Record immutable deterministic scenario snapshots |
| Contradiction | Preserve conflicting fields and flag possible asset-claim overlap |
| Counterparty | Contract only; private-core adapter is not connected |
| Disclosure | Explicit public-field projection under domain controls |
| Property page | Render the approved factual projection |
| Investor support | Contract only; no investment advice or external provider integration |

Future model adapters must emit schema-valid proposals and source IDs, have no general SQL or shell capability, and have no direct outbound communication or financial executor. The application authenticates the requesting actor independently of model output, resolves resource permission, evaluates policy and evidence, and records a human decision where required. A model's claim of approval is data, not permission.

Factory skills under `skills/` supply invariant review, hostile-document QA and vertical-slice verification. `factory_manifest.json` is a machine-readable staged-work contract. The executable factory gate is `scripts/release_check.py`; the broader factory is a maintained build/review workflow, not an unattended code-writing service.

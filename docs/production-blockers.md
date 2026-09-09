# Production readiness blockers

The V0 can demonstrate and test the synthetic transaction workflow. It cannot accept live investment, release real capital, assert investor eligibility, clear title or operate as a licensed intermediary. Setting an environment value must not remove these boundaries.

1. Replace the local standard-library HTTP host with an operated production service: TLS ingress, hardened identity/MFA/account recovery, rate limiting, monitoring, backup/recovery, secret management, deploy rollback and load tests.
2. Obtain qualified Ontario/Canada legal and compliance review of actual business activities, offering structures, investor eligibility, distribution, mortgage/real-estate licensing, privacy and records policy. Document accountable owners and evidence; pack names are not legal clearance.
3. Integrate licensed/contracted KYC/KYB, sanctions, registry/title, custody/trust, escrow/payment and professional-service providers as appropriate to the chosen business model. Validate callbacks and reconciliation before enabling any executor.
4. Operator-only isolated ClamAV scanning and passive PDF/CSV/XLSX review are implemented locally. Production scheduling, scanner refresh/health operations, additional format support and independent sandbox validation remain required. Test authorization and resource exhaustion across every download/preview/parser route.
5. Implement immutable external audit checkpoints, policy-content capture, state-transition completeness, revision/supersession workflows, professional authority checks and revocable granular disclosure.
6. Reconcile multiple deals per property, legal entity/instrument lifecycles and real settlement states. The current simulated ledger must never be relabelled as a legal ownership register.
7. Securely connect the private institutional network through a separate authenticated adapter and governed data contract. Validate consent/purpose/retention and source freshness. Do not copy it into public fixtures.
8. Pass independent security and transaction-domain review, real provider sandbox tests and an operational incident/recovery exercise. Human approval must refer to a concrete release hash and environment.

Product extensions such as automated outreach, startup fundraising analytics, additional jurisdictions, secondary liquidity and tokenization follow the protected vertical slice. None is required to prove this V0, and none is represented as live capability.

# Threat model

The principal assets are private property evidence, tenant boundaries, investor records, source integrity, policy decisions and publication scope. The attacker can be an authenticated user in another organization, a malicious document contributor, an injected browser payload, or a compromised dependency/build input. A local operating-system or database administrator remains outside the application's integrity guarantee.

| Threat | Current control | Remaining work before production |
|---|---|---|
| Document instructions or active content | Only bounded UTF-8 text/CSV; literal numeric parser; suspicious-pattern quarantine; no document execution or LLM tools | Isolated workers, malware scanning, content disarm, MIME/magic validation, resource limits, scanner health fail-closed policy |
| Hidden macros, polyglots, encrypted archives | PDF/Office/image/archive imports are not enabled | Do not enable merely by extending suffix allowlist; integrate tested parser/scanner adapters |
| Prompt injection | No LLM integration; uploaded bytes remain data; claims require human confirmation | Model-specific adversarial evaluations, separated tool authorization, retrieval provenance and egress controls |
| Cross-tenant reads/writes | Server checks organization ownership or explicit room permission | Independent penetration testing, production identity and comprehensive professional-role scopes |
| Client bypass of review | Gateway policy checks and reviewer separation | Dual control for live material actions, delegated authority expiry and revocation |
| Replayed financial request | Integer cents and request-bound idempotency | Real payment provider reconciliation, signed callbacks, reconciliation exceptions |
| False clear title | Unknown ownership/encumbrance status and asset-claim review flags | Authorized registry/title evidence, legal review, evidence expiry, beneficial ownership |
| Audit tampering | Hash chain, SQL immutability triggers | External append-only storage, signatures/checkpoints, backup and restore exercises |
| Private dataset publication | Explicit local allowlist, database magic detection, credential patterns, research canaries | Human exact-diff review, independently maintained secret scanning, data-loss prevention |

Quarantine is a heuristic, not an antivirus verdict. A PARSED artifact means only that the allowed parser accepted it. It does not establish authenticity, factual correctness, harmlessness under every other parser, legal validity, or freedom from fraud. There is no automatic override for quarantined evidence. Never test with live malware; use harmless synthetic instruction strings and parser-boundary fixtures.

Keep real documents and credentials out of the demo. Run with loopback binding. A production threat model must cover cloud IAM, encryption and key management, tenant-aware storage, retention/deletion, incident response, account recovery, abuse controls and operational access. Those controls cannot be supplied by a UI badge.

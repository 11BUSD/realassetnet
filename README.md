# Realassetnet V0

A Toronto/GTA-first, synthetic real-estate transaction workflow with evidence provenance, reproducible underwriting, independent publication review, controlled rooms, simulated participation and an audit ledger. The private institutional counterparty research remains outside this project.

**Status: local simulation, not a live investment platform.** No real KYC, custody, payment, issuance, transfer, legal clearance, appraisal certification, LLM, or external outreach integration is connected. The application refuses production mode. Public property discovery never grants offering access.

## Run

Requires Python 3.11 or later. The application uses the Python standard library and has no pip dependencies.

```powershell
cd C:\RealAssetNet\realassetnet-v0
python server.py --seed-demo
```

Open `http://127.0.0.1:8080`. The default listener is loopback. Demo accounts use `DemoOnly!2026`; see the [demo script](docs/demo-script.md). Use synthetic information only. Do not expose this server to the internet.

```powershell
python -m unittest discover -s tests -v
python scripts/scan_public.py --self-test
python scripts/release_check.py
```

The release check writes an exact source hash manifest and test evidence to `runtime/release_evidence.json`. It never deploys, pushes, merges or grants production approval. Runtime databases, logs and release evidence stay outside public exports. The default SQLite path is `runtime/app.sqlite`; set the process environment variable `RAN_DB` to choose another local simulation database. `.env.example` documents environment values; it is not automatically loaded.

## Implemented scope

The record inspector now expands beneath its row across the whole table, with structured readable fields and JSON download. The private network view uses separate operator-key authorization; see [private network setup](docs/private-network.md). New real-property records can be submitted privately with a source reference and contributor authority statement. They cannot be published or used for capital formation in this version.

PDF, DOCX, XLSX, PNG and JPEG files up to 5 MB can be retained as original bytes in private quarantine. This is storage, not malware clearance or extraction. Text/CSV numeric extraction remains the only active parser. Commercial income-property types are accepted; land and development deliberately require a separate feasibility model.

- Broker/owner signup and organization-scoped property intake within the Toronto market pack.
- Text/CSV numeric extraction, quarantine flags, explicit claim confirmation, missing/stale/conflicting evidence checks.
- Immutable underwriting snapshots with formula versions, evidence references and three scenarios.
- Reviewer-controlled public property passports and investor room grants.
- Simulated eligibility, property-only offering, subscription, holdings, fees and pro-rata distribution ledger.
- Permission checks, action decisions, audit hash-chain verification, deterministic agent envelopes and release checks.

The role catalog has more roles than the V0 workflows implement. Broker, investor and reviewer/admin accounts are provisioned for the demo; professional licensing is not verified by choosing a role. The schema separates property, deal, capital requirement, SPV, instrument, offering, holding and transaction. The current executor creates one simulated deal per property; historical multi-deal workflows are a subsequent implementation.

Read [architecture](docs/architecture.md), [invariants](docs/invariants.md), [threat model](docs/threat-model.md), [data dictionary](docs/data-dictionary.md), [agent contracts](docs/agent-contracts.md), [packs](docs/packs.md), and [factory roadmap](docs/factory-roadmap.md). [Production blockers](docs/production-blockers.md) distinguish current controls from required future infrastructure.

## Local container option

```powershell
docker build -t realassetnet-demo .
docker run --rm -p 127.0.0.1:8080:8080 realassetnet-demo
```

The container binds internally to all interfaces for Docker networking; the host port above remains loopback. Demo state is ephemeral when the container is removed. This Dockerfile is a local packaging convenience, not hardened production hosting. Review and pin the base-image digest before any controlled deployment.

## Publication boundary

Only this project directory is a possible public repository. Never initialize, publish or use a Docker build context at its parent workspace. `scripts/scan_public.py` checks an explicit project allowlist, refuses symlinks and unexpected root entries, detects database payloads and common credential/private-research patterns, and checks tracked files when this directory is its own Git repository. It does not prove the absence of all confidential information. Publication needs human review of the exact diff.

Three project-local factory skills live under `skills/`. They are review playbooks, not autonomous deployed agents or globally installed skills. `factory_manifest.json` defines bounded build stages and evidence contracts. Agents produce proposals; domain services retain execution authority.

Machine-readable interfaces: [OpenAPI contract](docs/openapi.json) and [agent envelope JSON Schema](docs/agent-envelope.schema.json). The OpenAPI contract documents current routes and deliberately partial private responses; domain authorization and action-dependent policy remain authoritative in the server.

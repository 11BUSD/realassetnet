# Provider control plane

The control plane records provider evidence separately from eligibility, financial state and legal approval. It includes a generic signed-review bridge receiver and a Trulioo demo-request adapter. Neither is configured or account-tested by default. Registry entries for title, custody/settlement and appraisal explicitly report NOT_IMPLEMENTED. Provider status never exposes secret values or claims a working account solely because credentials are present.

## Trulioo contract and limits

The adapter prepares a Canadian synthetic `Demo` request to the fixed HTTPS `POST /v3/business/verify` endpoint, including package ID, business fields and a customer reference. It uses an operator-supplied bearer token. These request and authentication fields were checked against the [official Business Verify reference](https://developer.trulioo.com/reference/post_v3-business-verify) on 2026-09-09. Business name, registration number, jurisdiction and the Essentials profile fields follow the [official verification guide](https://developer.trulioo.com/v1.0/docs/step-4b-verify).

Only synthetic Demo input is accepted. The adapter does not accept arbitrary URLs, callback URLs, live verification mode or a user-supplied consent list. It never assumes datasource consent. Package entitlements, account test entities, regional hosting requirements and matching rules must be confirmed with the provider. Credentials and account acceptance remain untested; having a request builder is not a completed production integration.

`prepare_trulioo_business(data, config)` creates the request and its digest without transmitting it. `execute_trulioo_business(data, authorization_reference, authorized_payload_sha256, config)` is a server-only transport requiring both enabled/outbound-enabled configuration, credentials and an exact approved request digest. Its caller must independently obtain and record Action Gateway authorization; an arbitrary reference string is not an approval. No HTTP route should call it directly from untrusted client parameters. There is no automatic dispatch.

The transport verifies HTTPS certificates, refuses redirects, ignores ambient proxy configuration, bounds timeout and response size, and does not retry automatically. An ambiguous transport failure stays an unknown outcome requiring reconciliation. Returned data includes response hash, vendor reference and a conservative normalized status; it does not store or return the raw provider response. It does not refresh OAuth tokens, implement native provider callbacks, retrieve async results, provide production retry reconciliation, or change investor eligibility. A `MATCH` is provider evidence requiring review, not authorization to transact.

## Local configuration

The optional excluded `runtime/providers.json` contains provider settings and environment-variable names, never secret values:

```json
{
  "signed_review_bridge": {
    "enabled": false,
    "webhook_secret_env": "RAN_REVIEW_BRIDGE_WEBHOOK_SECRET"
  },
  "trulioo_business": {
    "enabled": false,
    "outbound_enabled": false,
    "bearer_token_env": "RAN_TRULIOO_BEARER_TOKEN",
    "package_id_env": "RAN_TRULIOO_PACKAGE_ID"
  }
}
```

Keep process secrets in approved local secret-management configuration. Nothing generates a provider approval, obtains an account, incurs a paid verification or sends private data merely by loading this file. Provider status distinguishes DISABLED, UNCONFIGURED, CONFIGURED_NOT_VALIDATED and NOT_IMPLEMENTED. Production secret rotation, inbound rate limits, incident response and account verification remain operational responsibilities.

## Signed bridge receipt contract

`ingest_event(connection, "signed_review_bridge", rawbody, headers, config)` implements **Realassetnet's bridge protocol**, not a claim about Trulioo's native webhook signature. A separately trusted integration service would validate its upstream provider event and convert it to this minimal envelope. That bridge is not deployed here.

The body is exact UTF-8 JSON, at most 65,536 bytes, with these fields only:

```json
{
  "event_id": "synthetic-event-1",
  "subject_reference": "synthetic-subject-1",
  "event_type": "BUSINESS_VERIFICATION_RESULT",
  "occurred_at": "2026-09-09T12:00:00Z",
  "result": {"status": "match", "reference": "synthetic-provider-record"}
}
```

The opaque subject reference is not a business name, email or arbitrary document. Supported event types are BUSINESS_VERIFICATION_RESULT, IDENTITY_VERIFICATION_RESULT and DOCUMENT_CHECK_RESULT. Result status maps to PENDING, MATCH, NO_MATCH, REVIEW_REQUIRED, ERROR or UNKNOWN. Unrecognized values, including an unsupported approval label, remain UNKNOWN; original bounded status text is retained for review. Duplicate JSON keys, extra fields, unsupported event types and malformed references fail validation.

Use `X-RAN-Event-Timestamp` for decimal Unix seconds and `X-RAN-Event-Signature` for `sha256=` followed by lowercase HMAC-SHA256 hex. The signed bytes are `timestamp + "." + exact_raw_body`. The receiver compares signatures in constant time and accepts no more than 300 seconds of clock difference. Validate the raw body before JSON parsing; do not reconstruct JSON for signing. The configured shared secret must be at least 32 characters and must never appear in logs.

Event identity is unique per provider. A retry with identical body returns the existing receipt; reusing the event ID with different bytes is rejected. Fresh signature validation still applies to retries. The database stores normalized references, provider status, event/receipt timestamps, source payload hash and signature timestamp; it does not retain the raw webhook body. The caller owns the database transaction and audit event. The receiver inserts only a provider-event receipt and never updates eligibility, grants, offerings, holdings, transactions or distributions.

Tests use in-memory synthetic events and mocked outbound transport. They exercise invalid signatures, stale/future timestamps, idempotency conflict, disabled providers, UNKNOWN mappings, no eligibility/financial mutation, fixed endpoint, digest authorization and redirect denial. They do not constitute an external provider sandbox certification.

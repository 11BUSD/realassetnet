# Clerk identity boundary

Implemented, not activated: the user confirmed there is no existing Clerk application. No credentials, domain configuration or live session were supplied. Financial execution remains simulation regardless of identity provider. Nine tests pass in the application virtual environment, including an actual installed SDK rejection of a malformed token; the successful-identity cases use a mocked SDK boundary. This does not establish successful live JWT verification.

The optional dependency is `clerk-backend-api==7.0.0`, checked on PyPI on 2026-09-09. Install it in an isolated application environment, lock transitive dependencies and perform dependency scanning and real development-instance acceptance tests before release. Missing SDK fails closed for bearer authentication; the offline demo does not require it.

## Verification and authorization

`authenticate(headers, url, config=None)` passes only an explicit Authorization bearer header to the official SDK. Cookies are excluded. SDK options accept session tokens only, with exact authorized parties. After SDK verification, the adapter additionally checks the configured issuer, authorized origin, user subject and session ID. Returned claims exclude roles, email and metadata.

`resolve_user(connection, claims)` requires an ACTIVE mapping to an existing local user and matching local organization. Legacy `org_id` and v2 `o.id` verified claims are supported. Malformed, empty or conflicting organization claims deny; personal context applies only when neither organization claim is present. The active Clerk organization must exactly match the external organization in that mapping; an empty external organization explicitly selects personal-session context. Local application roles remain authoritative. Revoking the mapping denies subsequent requests immediately. This bounded model supports one organization context per external subject.

Upstream Clerk session/membership revocation synchronization still requires a production design and verified webhook or online-check integration. A valid signed token can remain valid until expiry. Signing in does not imply verified KYC or investment eligibility.

## Server contract

- Load and validate configuration at startup. Default mode is demo. Never fall back from Clerk to demo after an error.
- In Clerk mode ignore demo session cookies, authenticate the bearer, then resolve local membership. Missing bearer permits only anonymous routes; invalid supplied credentials deny.
- Disable demo login, signup, logout and demo seeding in Clerk mode. The frontend must use Clerk's SDK and attach its session token. Do not introduce a production token-paste field.
- Retain origin/fetch-site checks. Bearer requests do not use the demo-cookie CSRF mechanism. Cookie authentication would require its own CSRF design.
- Expose only `public_config()`, never full config. Its frontend fields include publishable key, issuer and authorized parties, never the secret. Issuer validation allows only an ASCII HTTPS domain with optional port 443, suitable for use as an exact CSP source. Keep raw credentials out of audits, URLs and logs. Apply existing tenant authorization and Action Gateway after mapping.
- Use a production HTTPS server/proxy and explicit allowed hosts. This adapter does not make the local simulation HTTP server production-ready.

## Migration contract

Root integration supplies `external_identities`: provider, issuer, subject, user_id (users FK), organization_id (organizations FK), external_organization_id (non-null, empty for personal context), state (ACTIVE/REVOKED), created_by, created_at, updated_at. Primary key is `(provider, issuer, subject)`. Operator provisioning/revocation appends audit events.

## Operator setup

Required account information: Clerk application access, environment-specific publishable and secret keys, exact HTTPS issuer, approved application origins, real Clerk user and organization IDs. Production also requires the production instance, domain/DNS access, sign-in/MFA/session policies and verified frontend/backend integration. Do not paste secrets into chat or commit them.

`scripts/configure_identity.py configure` accepts an external configuration path, issuer, repeatable origin and publishable key. It prompts invisibly for the secret and creates the file exclusively outside the application directory. Restrict Windows ACLs to the operator/service identity: POSIX creation mode alone does not configure Windows ACLs. Set `RAN_IDENTITY_CONFIG` to that file. Environment overrides are `RAN_IDENTITY_MODE`, `CLERK_ISSUER`, `CLERK_AUTHORIZED_PARTIES` (comma-separated), `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`.

The local operator CLI requires database filesystem access and an existing local admin actor ID. `provision-user` creates a user in an existing organization with an explicit role and undistributed random password. `map` associates an exact external subject and optional organization with an existing app user. `revoke` disables that association. Existing mappings cannot be silently replaced. These operations never create Clerk accounts or grant roles based on email domains. Production needs an initial admin/bootstrap ceremony; synthetic reviewer credentials are not production administrator credentials.

## Primary references

The implementation follows the official [Python SDK](https://github.com/clerk/clerk-sdk-python), [authentication source](https://github.com/clerk/clerk-sdk-python/blob/main/src/clerk_backend_api/security/authenticaterequest.py) and [options source](https://github.com/clerk/clerk-sdk-python/blob/main/src/clerk_backend_api/security/types.py). Clerk's SDK handles token verification; this adapter adds stricter instance and local membership checks. Also see the [Python integration guide](https://clerk.com/articles/how-to-add-authentication-to-a-python-backend) and [production deployment guide](https://clerk.com/docs/guides/development/deployment/production). Sources checked 2026-09-09. Verify pinned-package behavior before deployment.

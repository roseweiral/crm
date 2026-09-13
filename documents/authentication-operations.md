# Authentication and authorization operations

## Implemented security boundary

The CRM uses OpenID Connect authorization code flow with PKCE for Google and
Microsoft. Discovery metadata supplies the provider endpoints and signing keys.
The callback validates provider signatures, audience, issuer, expiry, state, nonce,
and the PKCE verifier through Authlib. A new identity also requires an unexpired,
single-use invitation whose normalized email matches the provider's verified email.

Provider tokens are not returned to React. FastAPI creates a random CRM session,
stores only its SHA-256 hash, and gives the browser a secure HTTP-only cookie. Sessions
expire after 12 hours and can be revoked. Invitations expire after seven days.
The application uses one `SESSION_LIFETIME` value for both the persisted expiry and
cookie lifetime. The database retains the same 12-hour default as a safety net, with
a contract test guarding against drift.

The public endpoints are `/health`, `/auth/providers`, `/auth/login/{provider}`, and
`/auth/callback/{provider}`. All `/api/v1` CRM data endpoints require authentication,
including `/api/v1/me`. Sign-out revokes the server-side session and removes the
browser cookie. The authenticated application displays a **Switch user** action;
it signs out, clears any invitation from the browser URL, and returns to the social
sign-in page so a different fake identity can be selected.

`GET /api/v1/me` also returns every current role for the signed-in contact. Access
roles are shown without a group, organization roles include their assigned group,
and family relationships are shown as Parent, Child, Guardian, or Other. Ended role
assignments are excluded.

## Provider configuration

The environment templates document these values for each provider:

Google and Microsoft are the deliberately fixed provider catalogue for this release.
Adding another provider requires adding it to `OIDC_PROVIDERS` and explicitly
defining how that provider proves an email address; environment variables alone do
not enable an unknown provider.

- `OIDC_GOOGLE_METADATA_URL`, `OIDC_GOOGLE_CLIENT_ID`, and
  `OIDC_GOOGLE_CLIENT_SECRET`;
- `OIDC_MICROSOFT_METADATA_URL`, `OIDC_MICROSOFT_CLIENT_ID`, and
`OIDC_MICROSOFT_CLIENT_SECRET`; and
- `AUTH_SESSION_SECRET`, a high-entropy secret used only to sign the short-lived OIDC
  transaction cookie.

Production redirect URIs registered with each provider must be the externally visible
`/auth/callback/google` and `/auth/callback/microsoft` URLs. Production must use HTTPS.
Secrets belong in the deployment secret store and must not be committed.

## First administrator and invitations

On a production database with contacts but no access-role assignments, the trusted
operator creates the first administrator invitation inside the application container:

```shell
python bootstrap_admin.py CONTACT_UUID
```

The command refuses to run once any access-role assignment exists. It creates the
minimum permission and Global System Administrator role, an invited account, a
single-use invitation, and an audit event, then prints the invitation URL once. It
does not create a password or permanent bypass.

After bootstrap, a Global System Administrator creates invitations with
`POST /api/v1/invitations` and a contact UUID. Creating a new invitation revokes any
previous unused invitation for that account. The response contains the manual-delivery
URL; the raw invitation secret is never stored in the database.

Google supplies an `email_verified` claim, which is required. Microsoft Entra ID does
not normally emit that flag; for Microsoft, the application accepts the email (or
`preferred_username`) asserted by the configured tenant after the ID token has passed
issuer, signature, audience, nonce, and expiry validation. The production metadata
URL is therefore tenant-specific. Supporting personal Microsoft accounts or multiple
tenants requires a separate policy decision.

## Fake OIDC service

`fake-oidc/` is a separate development and test service. It implements discovery,
authorization, token, and JWKS endpoints and generates an ephemeral RSA signing key
each time it starts. It is enabled only by the `development` and `test` Compose
profiles and is not referenced by the production provider configuration.

The development issuer is `http://localhost:9000`, allowing a host browser to display
the identity chooser. The isolated test issuer is `http://fake-oidc:9000`, allowing
the API tester and browser container to complete the same redirects without internet
access. The service reads `database/seed/contacts.csv` and offers every seeded
contact in the chooser. Each displayed contact has a fictional email, an active
account, and a Google fake-provider identity; unlinked test personas are not shown.
These identities are development and test fixtures only.

The fake provider is never an authentication bypass. The application performs the
same discovery, PKCE, state, nonce, signature, issuer, audience, expiry, and verified
email checks used for real providers.

## Current authorization rules

The application evaluates these rules through `AuthorizationService`. Its active,
human-readable policy is `app/policies/authorization.toml`; PostgreSQL remains the
source of truth for the roles, dates, hierarchy, and family relationships referenced
by that policy.

- The seeded first contact has an explicit Global System Administrator assignment and
  can read all CRM information.
- Current Group Leader and Area Manager assignments can read contacts and groups in
  the assigned group and all descendant groups.
- Every account can read its own contact record.
- A parent can read contacts in their family units. Guardian behavior remains an
  explicit deferred authorization decision.
- An ended organisational assignment stops contributing scope immediately because
  dates are evaluated on every request.
- Archived contacts and inactive accounts cannot establish or use sessions.

Collection queries are scoped before pagination and totals are calculated. Detail
routes return `404` for records outside the effective scope so they do not disclose
record existence.

## Automated tests

Most API tests create a random short-lived CRM session directly in the session store;
only its hash is persisted. This keeps regression tests fast while exercising the
production session and authorization dependencies. A focused contract test completes
the real authorization-code exchange against the fake provider. Separate regression
coverage proves that a Group Leader receives their descendant subtree without access
to another branch.

## Threat model summary

Controls currently address stolen browser-readable tokens, provider-token leakage,
authorization-code interception, callback forgery, token replay, invitation theft and
reuse, session database disclosure, account enumeration, expired roles, archived
contacts, and cross-branch record access.

Operational risks still requiring deployment controls include compromise of provider
client secrets or the OIDC transaction secret, an administrator's external account,
the host or database, and incorrect contact/role/family data. Secret rotation,
database backups, HTTPS termination, security monitoring, administrator recovery, and
retention rules must be defined before production launch.

### Verified email and account recovery

New identity links require an explicit `email_verified=true` claim and an `email`
matching the invitation. `preferred_username` is not an email-verification signal.
Microsoft Entra's ordinary email/username claims do not establish mailbox ownership:
see [Microsoft's ID token claim reference](https://learn.microsoft.com/en-us/entra/identity-platform/id-token-claims-reference).
Until an independent mailbox-verification flow is implemented, providers that do
not supply verified email cannot accept invitations. The test OIDC provider emits
verified email and supports testing both configured provider names.

Already-linked identities sign in using their validated provider, issuer, and
subject. Missing or unverified email claims do not replace the stored verified
address or block that existing identity's sign-in.

Invitation acceptance locks and checks the account before consuming the invitation.
Only `invited` accounts can activate. Invitation creation returns 409 for active,
suspended, closed, or already-linked accounts; reopening those accounts requires a
separately designed recovery flow. Failed OIDC exchange and identity-verification
audit events commit independently from the rejected request transaction.

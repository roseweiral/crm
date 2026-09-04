# Authentication and authorization

## Status

This document records the initial design decisions for authentication (AuthN) and
authorization (AuthZ) in the Volunteer CRM. It is a living design document; open
questions should be resolved here before implementation begins.

The account, identity, invitation, session, Google/Microsoft OIDC, fake-provider,
endpoint protection, audit, and initial read-authorization foundations are now
implemented. Detailed write permissions and the remaining family and multi-group
edge cases must be resolved before write endpoints are introduced.

## Agreed principles

- CRM access is invitation-only. Signing in successfully with an external provider
  does not create a CRM account automatically.
- Users authenticate with an external identity provider rather than a CRM username
  and password.
- Google and Microsoft are the initial providers. Additional providers should be
  introduced only when there is a demonstrated user need.
- Invitations are provider-neutral. The invited person may authenticate with any
  provider currently enabled by the CRM.
- The verified email returned by the selected provider must match the email address
  on the invitation.
- Invitations are delivered as manually copied links in the initial release.
- Young members may be invited; login eligibility is not restricted to adult
  contacts.
- Invitations remain valid for one week unless consumed or revoked sooner.
- Browser sessions last for 12 hours. A persistent "remember me" option is not part
  of the initial release.
- Each account has one external identity. Linking additional providers is deferred
  until an explicit account-linking process is designed.
- A CRM contact, an application user account, and an external identity are separate
  concepts, even when they belong to the same person.
- External identities are matched using the provider's stable issuer and subject
  identifiers. Email addresses are attributes, not permanent identity keys.
- Authentication tokens from external providers remain on the server. The browser
  receives a secure, HTTP-only application session cookie.
- Authorization is enforced by the API and its database queries, not only by the
  React interface.
- Organisational roles and security roles are related but distinct. A role such as
  Group Leader must not silently acquire new system permissions when either model
  changes.

## First administrator

The first administrator is established through a one-time bootstrap operation run
by the trusted system operator in the deployed application environment.

The bootstrap operation will:

1. Select an existing contact, or create the contact through an explicitly designed
   administrative operation if no suitable contact exists.
2. Create that contact's application user account in an invited state.
3. Create a single-use, short-lived invitation.
4. Assign the account the System Administrator access role.
5. Output the invitation link once so the operator can deliver it to the intended
   person through a trusted channel.
6. Write an audit event recording when and where the bootstrap was performed.

The administrator follows the invitation link and signs in with Google or Microsoft.
The application validates the invitation, completes the provider flow, links the
external identity to the invited account, consumes the invitation atomically, and
starts a normal application session.

The bootstrap mechanism is not a separate login method. It does not create a local
password, accept a permanent environment-variable identity, or leave a bypass in
the running application. It must refuse to run after the initial administrator has
been established unless a separately designed recovery procedure is invoked.

Deployment access must not automatically imply CRM access. Conversely, losing the
first administrator's external identity must be handled through an audited recovery
process rather than by re-enabling the original bootstrap path casually.

## Invitation flow

An administrator selects an existing contact and invites that person to become a
user. The system creates a short-lived, single-use invitation containing a random
secret whose stored representation is hashed. The invitation is bound to the
intended user account and email address.

Following the link does not authenticate the person by itself. The recipient must
choose and complete sign-in with any enabled provider. The inviter does not select
the provider. On success, the application requires the provider to report a verified
email address matching the invitation email, links the provider identity to the
invited account, and consumes the invitation in one database transaction.

The initial release displays the invitation link to the administrator once for
manual delivery through a trusted channel. Automated email delivery can be added
later without changing the invitation or acceptance model.

A person who visits a normal sign-in page with an identity that is not already linked
to an active account is denied access and given a neutral message explaining that an
invitation is required. The response must not reveal whether a particular contact or
email address exists in the CRM.

Automatic account linking based only on matching email addresses is not permitted.
Adding a second provider to an existing account requires an authenticated account
linking flow or an administrator-assisted recovery process.

## Proposed application model

The detailed schema is not yet agreed, but the design is expected to introduce:

- `user_accounts`, linked to contacts and carrying lifecycle state such as invited,
  active, suspended, or closed;
- `user_identities`, containing provider, issuer, subject, and provider-supplied
  profile attributes;
- `invitations`, containing expiry, consumption, inviter, and a hash of the invitation
  secret;
- `user_sessions`, supporting expiry, revocation, and sign-out;
- `permissions` and `access_roles`;
- scoped user access-role assignments;
- `audit_events` for security-sensitive activity.

The existing `contacts.can_login` flag is insufficient as the long-term account
lifecycle model. It may be retained temporarily during migration, but account status
should become the source of truth.

Archiving a contact immediately prevents that contact's account from logging in and
invalidates its existing sessions. A person who is no longer a contact cannot retain
CRM access.

## Authentication flow

The React application initiates sign-in through the FastAPI service. FastAPI performs
the authorization-code flow with the selected provider, validates the returned
identity, and establishes a server-managed CRM session. Provider access and identity
tokens are not exposed to React or stored in browser storage.

The browser session cookie should be secure, HTTP-only, use an appropriate SameSite
policy, and be protected against session fixation and cross-site request forgery.
Production should preferably serve the frontend and API under the same site, even if
they are separate services internally.

An authenticated endpoint such as `/api/v1/me` will return the signed-in user's basic
profile and effective capabilities. It will not be the sole authorization control;
every protected endpoint will enforce its own policy.

## Authorization direction

Authorization decisions answer both what a user may do and where they may do it.
Access is expected to be composed from:

- fine-grained permissions, for example `contacts.read` or `roles.manage`;
- access roles that group permissions, for example Viewer, Group Administrator, or
  System Administrator;
- assignments of an access role to a user, optionally scoped to an organisational
  group and its descendants; and
- dates and account state that determine whether an assignment is currently active.

A group-scoped assignment includes descendant groups by default. The exact rules
for exceptions, conflicting assignments, and unusual hierarchy cases remain part of
the detailed authorization design.

The existing contact, role type, group, and role-assignment data can inform access,
but any mapping from an organisational role to an access role must be explicit and
reviewable. When permission is derived from an organisational role, it ends
automatically when that role assignment ends. Authorization checks must evaluate
the role dates at request time; removing access must not depend on a delayed cleanup
job. Independently granted access, such as System Administrator, follows the dates
and lifecycle of its own access-role assignment.

The initial authorization rules are:

- Global System Administrator can see all CRM information across the organisation.
- Group Leader can see all information belonging to their assigned group and every
  descendant group.
- Area Manager can see all information belonging to their assigned group and every
  descendant group.
- A child account can see only its own contact data.
- A parent can see their own data and the data of contacts connected to the same
  family unit.

The meaning of "all information" and the boundary of data "belonging" to a group
must be defined per resource before write operations are introduced. Family access
also needs an explicit rule for which family relationships count as a parent and
what happens when contacts belong to multiple family units.

The first contact in the curated seed data is the development and test Global System
Administrator. This is fixture behavior only: row order must never grant permissions
in a live system, and production initialization uses the first-administrator
bootstrap process.

Protected collection endpoints must filter records to the user's permitted scope.
Detail endpoints must apply the same scope. A missing authentication session returns
`401`; an authenticated user attempting a known but forbidden action returns `403`,
except where concealing record existence requires a `404` response.

The health endpoint and the minimum endpoints required to begin and complete sign-in
remain public. Existing CRM data endpoints become protected.

## Automated testing strategy

Regression tests do not use live Google or Microsoft accounts and do not store known
provider private keys. Authentication and authorization testing is divided into two
boundaries:

1. Provider-flow tests use a controlled fake OpenID Connect provider to exercise
   redirects, state and nonce validation, verified-email handling, callback failures,
   and identity creation.
2. API regression tests use stable seeded contacts, user accounts, role assignments,
   and group relationships. Test setup creates short-lived application sessions
   directly in the session store and supplies the resulting cookie to API requests.

Session secrets are generated for each test run and only their hashes are stored in
the database. Tests may use stable user UUIDs and descriptive helpers such as
`global_admin_session`, `area_manager_session`, `group_leader_session`,
`parent_session`, and `child_session`; they do not require stable authentication
secrets.

This exercises the production session lookup, account-status checks, role dates,
permission evaluation, and query scoping. It avoids adding a test-only login endpoint
or authentication bypass to the application. The test data must contain users in
different branches of the hierarchy so the suite proves both allowed access and
cross-branch denial.

The minimum authorization fixture set includes:

- one Global System Administrator;
- one Area Manager with descendant groups and an out-of-scope branch;
- one Group Leader;
- one parent and related child;
- one child account;
- one ordinary contact with no privileged role;
- one user whose organisational role has ended; and
- one archived contact with an otherwise valid session record.

End-to-end browser tests can install the same short-lived application session cookie
in the browser context. A small number of separate browser tests cover the visible
invitation and provider-selection journey using the fake provider.

## Suggested delivery slices

1. Agree the account, invitation, session, and audit model.
2. Implement and test the initial-administrator bootstrap operation.
3. Implement invitation acceptance and Google and Microsoft sign-in.
4. Add session management, `/api/v1/me`, sign-out, expiry, and revocation.
5. Require authentication for all CRM data endpoints.
6. Agree the permission catalogue, access roles, and group-scope semantics.
7. Enforce authorization in API queries and add cross-scope security tests.
8. Add administrative user and access-management screens.

## Open questions

1. Which organisation owns the CRM, and do most intended users have managed Google
   Workspace or Microsoft 365 accounts? This affects provider configuration and
   whether tenant or domain restrictions are appropriate.
2. Are there cases where a descendant group must be excluded from an otherwise
   inherited parent-group assignment?
3. Precisely which resources belong to a group, particularly contacts who have roles
   in multiple groups and family members spanning group boundaries?
4. Are Group Leader and Area Manager initially read-only, or will either role receive
   write permissions when write endpoints are introduced?
5. What audited recovery process should be available if all system administrators
   lose access?
6. If an invited contact has no email address yet, should creating the invitation
   also update the contact's email, or must the contact be updated first?
7. Does a `guardian` family relationship receive the same access as `parent`, and can
   either relationship view every family member or only children?
8. When a child becomes an adult, should family visibility change automatically?
9. Does the 12-hour session expire absolutely after 12 hours, or may active use renew
   it up to a separate maximum lifetime?

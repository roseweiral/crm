# API

This directory contains the FastAPI application for the CRM. `GET /health` remains
public so Docker and the test runner can verify availability. Authentication entry
points are also public; every CRM data endpoint requires a valid server-side session.

The first read-only API routes are:

- `GET /api/v1/contacts`
- `GET /api/v1/contacts/{contact_id}`

Authentication endpoints include:

- `GET /auth/providers`
- `GET /auth/login/{provider}`
- `GET /auth/callback/{provider}`
- `GET /api/v1/me`
- `POST /auth/sign-out`
- `POST /api/v1/invitations` (Global System Administrator only)

Authorization decisions go through `AuthorizationService` in `authorization.py`.
The commented `policies/authorization.toml` file defines which access roles,
organisational roles, and family relationships grant each action. PostgreSQL owns
the underlying membership facts; the policy file controls what those facts allow.

Google and Microsoft use OpenID Connect authorization code flow with PKCE. Provider
tokens remain on the server and are exchanged for a revocable CRM session cookie.
Authorization scope is calculated from the explicit Global System Administrator
assignment, current Group Leader or Area Manager assignments and descendant groups,
the signed-in contact, and parent family relationships.

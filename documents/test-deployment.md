# Internet-facing test deployment

## Status and intent

This deployment is for demonstrations and acceptance testing with fictional data.
It is not the production architecture and must not be used for real personal data.
The configuration is provider-neutral and runs on one Docker host with public ports
80 and 443.

## Decisions

- Keep local development in `compose.yaml`; use the separate
  `compose.test.yaml` stack for the public test environment.
- Put the application and fake identity provider behind HTTPS using Caddy.
- Put both public hostnames behind HTTP Basic Authentication. The username is fixed
  as `tester`; only the password needs to be distributed to testers.
- Continue using fake OIDC. After passing the outer gate, a tester may choose any
  eligible fictional identity, including identities with broad permissions.
- Expose only Caddy on ports 80 and 443. PostgreSQL, FastAPI, the static frontend,
  and fake OIDC remain on the private Compose network.
- Import the complete committed seed dataset, including its known users, then add
  a larger deterministic demo dataset once for a new PostgreSQL volume. Container
  restarts and application deployments preserve subsequent changes.
- Treat deleting the Compose volumes as the explicit database reset operation.
- Serve the compiled React application with Nginx and run FastAPI without live
  reload. The local development containers retain Vite and live reload.
- Store deployment secrets only in an ignored environment file on the server.

The fake provider is deliberately not real authentication. The shared gate limits
casual public access, but everyone with its password can impersonate every demo
identity. Rotate the gate password if it is shared beyond the intended test group.

## Public names

Two DNS names are required and must both resolve to the Docker host:

- `TEST_APP_HOST`, for example `crm-test.example.org`
- `TEST_OIDC_HOST`, for example `login.crm-test.example.org`

Caddy obtains and renews TLS certificates automatically. Both inbound TCP ports 80
and 443 must be allowed; UDP 443 may also be allowed for HTTP/3. Do not allow public
access to ports 5432, 8000, 8080, 5173, or 9000.

## Initial configuration

Copy `.env.test-deployment.example` to `.env.test-deployment` on the server and
replace every placeholder. Generate random application secrets with a password
manager or another cryptographically secure generator.

Generate the gate password hash locally or on the server:

```shell
docker run --rm caddy:2.10.2-alpine caddy hash-password
```

Enter the chosen password when prompted. Put the returned hash in
`TEST_GATE_PASSWORD_HASH` enclosed in single quotes, because bcrypt hashes contain
dollar signs. Testers use username `tester` and the original password; the clear
text password is not stored in the deployment environment.

## Deploy and update

From the repository root:

```shell
docker compose --env-file .env.test-deployment -f compose.test.yaml up --build -d
docker compose --env-file .env.test-deployment -f compose.test.yaml ps
```

The first start performs these operations in order:

1. PostgreSQL creates its schema and imports the complete committed test seed data.
2. `demo-loader` retains those records and adds a larger deterministic dataset of
   180 contacts, 45 families, and 18 local groups. Overlapping generated records
   are ignored, the seed authorization configuration is retained, and new demo
   contacts receive selectable fake identities. The known seed identities are
   retained and pointed at the test environment's public fake-provider issuer.
3. `demo-loader` records a successful initialization marker in the audit log.
4. The API, fake identity provider, compiled frontend, and HTTPS gateway start.

On later starts, `demo-loader` sees the marker and leaves the database unchanged.
Use the same `up --build -d` command to deploy a later revision.

Inspect service output when diagnosing a failed deployment:

```shell
docker compose --env-file .env.test-deployment -f compose.test.yaml logs --tail=200
```

## Reset the fictional dataset

This operation permanently deletes the test database and Caddy's local certificate
state. It is intentional and should be used only when a clean demo dataset is
wanted:

```shell
docker compose --env-file .env.test-deployment -f compose.test.yaml down --volumes
docker compose --env-file .env.test-deployment -f compose.test.yaml up --build -d
```

Ordinary `down`, `stop`, `restart`, and deployment updates do not delete the named
volumes.

## Deferred production concerns

Before handling real data, replace fake OIDC, use a managed or independently backed
up database, add monitoring and restore testing, define patching and incident
procedures, and review privacy, retention, and access-control requirements.

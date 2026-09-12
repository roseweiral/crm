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
- Put the application hostname behind HTTP Basic Authentication. The username is
  fixed as `tester`; only the password needs to be distributed to testers.
- Leave the fake OIDC hostname outside the password gate so the browser does not
  prompt again while redirecting between the application and identity provider.
  A tester who has passed the application gate may choose any eligible fictional
  identity, including identities with broad permissions.
- Expose only Caddy on ports 80 and 443. PostgreSQL, FastAPI, the static frontend,
  and fake OIDC remain on the private Compose network.
- Import the complete committed seed dataset, including its known users, then add
  a larger deterministic demo dataset once for a new PostgreSQL volume. Container
  restarts and application deployments preserve subsequent changes.
- Treat deleting the Compose volumes as the explicit database reset operation.
- Serve the compiled React application with Nginx and run FastAPI without live
  reload. The local development containers retain Vite and live reload.
- Store deployment secrets only in an ignored environment file on the server.

The fake provider is deliberately not real authentication. Its sign-in page and
fictional identity list are publicly reachable, but returning to and using the CRM
still requires the application gate password. Everyone with that password can
impersonate every demo identity. Rotate the gate password if it is shared beyond
the intended test group. Do not use this arrangement for real personal data.

## Public names

Two DNS names are required and must both resolve to the Docker host:

- `TEST_APP_HOST`: `crm-test.roseweir.com`
- `TEST_OIDC_HOST`: `login.crm-test.roseweir.com`

The parent domain `roseweir.com` is registered and its DNS is managed through
Bluehost. The existing apex-domain, website, mail, and other DNS records are not
part of this deployment and must remain unchanged.

Caddy obtains and renews TLS certificates automatically. Both inbound TCP ports 80
and 443 must be allowed; UDP 443 may also be allowed for HTTP/3. Do not allow public
access to ports 5432, 8000, 8080, 5173, or 9000.

## Hetzner infrastructure provisioning

The deployable test root is defined in
`infrastructure/terraform/environments/test`; it calls the reusable
`infrastructure/terraform/modules/hetzner-host` module. Terraform owns:

- the Ubuntu cloud server and configurable server size and location;
- stable public IPv4 and IPv6 resources;
- the Hetzner firewall and its server attachment;
- registration of the operator's SSH public key;
- optional Hetzner backups and deletion protection; and
- cloud-init preparation of Docker, automatic security updates, the non-root
  deployment user, and the application directory.

The Hetzner project and API token remain account-level prerequisites. Bluehost DNS
is outside this Terraform stack, so Terraform outputs the A and AAAA values to add
there manually.

After `terraform apply`, use the `required_ipv4_dns_records` output to create these
records in Bluehost:

| Type | Bluehost host/name | Value |
| --- | --- | --- |
| A | `crm-test` | Terraform's `server_ipv4` output |
| A | `login.crm-test` | Terraform's `server_ipv4` output |

Use Bluehost's default TTL. Optionally create matching AAAA records using the
`required_ipv6_dns_records` output. Confirm that both public names resolve to the
new server before starting the Compose gateway, otherwise Caddy cannot obtain its
public TLS certificates.

Infrastructure settings such as the server size, location, domains, repository,
and code ref are Terraform variables. The Hetzner token, SSH public key, and SSH
source CIDRs are injected at runtime. Private SSH keys and application secrets are
never passed through Terraform because values rendered into cloud-init are stored
in Terraform state.

See [`infrastructure/terraform/README.md`](../infrastructure/terraform/README.md)
for setup, plan, apply, and destroy commands.

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
dollar signs. Testers use username `tester` and the original password for the CRM
hostname only; the clear text password is not stored in the deployment environment.

## Deploy and update

From the repository root:

```shell
docker compose --env-file .env.test-deployment -f compose.test.yaml up --build -d
docker compose --env-file .env.test-deployment -f compose.test.yaml ps
```

Terraform prepares the host but deliberately does not perform these application
deployment commands. This keeps infrastructure changes separate from routine code
releases and prevents application secrets from entering Terraform state.

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

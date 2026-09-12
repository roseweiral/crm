# Production environment placeholder

This directory reserves an independent Terraform root and state boundary for the
future production environment. It intentionally instantiates no modules and
creates no resources.

Before production infrastructure is defined, decide and document:

- production domain names and DNS ownership;
- real Google and Microsoft OIDC configuration;
- whether PostgreSQL is colocated, separately hosted, or managed;
- server topology, size, region, availability, and scaling expectations;
- backup schedule, off-server storage, retention, encryption, and restore tests;
- monitoring, alerting, log retention, and incident response;
- deployment promotion and rollback strategy;
- network administration access and operator responsibilities; and
- deletion protection and Terraform state backend controls.

Production must use its own state and secrets. Do not copy the test state, test
fake OIDC service, test data initialization, or test password gate into this root.
The reusable `../../modules/hetzner-host` module may be used later if the resulting
production design calls for the same single-host foundation.

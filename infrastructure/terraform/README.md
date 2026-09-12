# Terraform infrastructure

Terraform is separated into reusable modules and independently stateful environment
roots:

```text
infrastructure/terraform/
├── modules/hetzner-host/
└── environments/
    ├── test/
    └── production/
```

`environments/test` is deployable. It provisions the single Hetzner Cloud host,
stable public addresses, firewall, SSH public-key registration, and first-boot host
preparation.

`environments/production` is intentionally empty except for its version constraint
and decision record. It cannot create resources until a production design is
agreed and a module is explicitly instantiated.

Application containers and application secrets are intentionally outside
Terraform. Terraform prepares Docker and the deployment directory; the deployment
procedure then installs `.env.test-deployment` and starts `compose.test.yaml`.

## Prerequisites

- Terraform 1.8 or later
- A Hetzner Cloud project
- A read/write API token scoped to that project
- An existing SSH key pair
- Access to the Bluehost-managed DNS for `roseweir.com`

Do not place API tokens, private SSH keys, database passwords, session secrets, or
the test-gate password in Terraform files. Terraform state is local by default and
must not be committed.

## Runtime configuration

The Hetzner provider reads its token directly from `HCLOUD_TOKEN`. Supply the SSH
public key and trusted SSH source networks using Terraform environment variables:

```shell
export HCLOUD_TOKEN="replace-with-project-api-token"
export TF_VAR_ssh_public_key="$(ssh-keygen -y -f /path/to/private-key)"
export TF_VAR_ssh_allowed_cidrs='["203.0.113.10/32"]'
```

The private key remains outside Terraform. Replace the example address with the
public IPv4 or IPv6 CIDR from which administration will occur. A `/32` restricts
IPv4 SSH access to one address; a `/128` does the equivalent for IPv6.

Copy `environments/test/terraform.tfvars.example` to
`environments/test/terraform.tfvars` and set the non-secret deployment values.
Real `.tfvars` files are ignored by Git.

## Plan and create

```shell
cd infrastructure/terraform/environments/test
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

Review every plan before applying it. Creating resources begins Hetzner billing.
After apply, Terraform outputs the server addresses, SSH command, public URLs, and
the DNS A and AAAA records to add to Bluehost. The configured names default to
`crm-test.roseweir.com` and `login.crm-test.roseweir.com`.

Cloud-init can take several minutes after the server becomes reachable. Inspect it
after connecting:

```shell
sudo cloud-init status --wait
sudo cloud-init status --long
```

## Destroy

```shell
terraform plan -destroy
terraform destroy
```

Destroying the test stack deletes the server and primary IP resources. Any application
database stored only on that server is consequently lost. `protect_server=true`
must be changed and applied before Terraform can destroy a protected server.

## Deliberate boundaries

- Test and production use different Terraform roots and state files. Never switch
  environments by changing an `environment` variable in one state.
- The Hetzner project and project API token are created manually.
- DNS remains manually managed in Bluehost. Terraform outputs the required records
  and does not alter any existing `roseweir.com` website or mail records.
- Cloud-init installs Docker but does not clone private code or receive deployment
  secrets. This keeps credentials out of Terraform state.
- Routine code releases use the application deployment process, not Terraform.
- Changing cloud-init or SSH keys on an existing server may require replacement;
  always inspect the plan.

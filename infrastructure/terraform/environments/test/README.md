# Test environment

This is the deployable Terraform root for the internet-facing test environment.
Its state must never be shared with another environment.

Runtime credentials and SSH inputs:

```shell
export HCLOUD_TOKEN="replace-with-project-read-write-token"
export TF_VAR_ssh_public_key="$(ssh-keygen -y -f /path/to/private-key)"
```

State is stored in the `alroseweir/volunteer-crm-test` HCP Terraform workspace,
which must be configured for Local execution. Test deliberately permits global
key-only SSH access so GitHub-hosted runners can deploy.

Plan from this directory:

```shell
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Only run `terraform apply` after reviewing the plan and accepting that creating
the server and IP resources starts billing.

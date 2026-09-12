# Test environment

This is the deployable Terraform root for the internet-facing test environment.
Its state must never be shared with another environment.

Runtime credentials and SSH inputs:

```shell
export HCLOUD_TOKEN="replace-with-project-read-write-token"
export TF_VAR_ssh_public_key="$(ssh-keygen -y -f /path/to/private-key)"
export TF_VAR_ssh_allowed_cidrs='["203.0.113.10/32"]'
```

Plan from this directory:

```shell
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Only run `terraform apply` after reviewing the plan and accepting that creating
the server and IP resources starts billing.

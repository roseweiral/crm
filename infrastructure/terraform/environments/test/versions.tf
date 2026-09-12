terraform {
  required_version = "= 1.16.2"

  cloud {
    organization = "alroseweir"

    workspaces {
      name = "volunteer-crm-test"
    }
  }

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.69.0"
    }
  }
}

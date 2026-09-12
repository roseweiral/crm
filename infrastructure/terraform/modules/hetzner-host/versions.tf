terraform {
  required_version = ">= 1.8.0, < 2.0.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = ">= 1.69.0, < 2.0.0"
    }
  }
}

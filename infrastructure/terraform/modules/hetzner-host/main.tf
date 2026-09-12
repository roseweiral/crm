locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  common_labels = {
    application = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "hcloud_ssh_key" "deployment" {
  name       = "${local.resource_prefix}-deployment"
  public_key = trimspace(var.ssh_public_key)
  labels     = local.common_labels
}

resource "hcloud_primary_ip" "ipv4" {
  name        = "${local.resource_prefix}-ipv4"
  type        = "ipv4"
  location    = var.server_location
  auto_delete = false
  labels      = local.common_labels
}

resource "hcloud_primary_ip" "ipv6" {
  name        = "${local.resource_prefix}-ipv6"
  type        = "ipv6"
  location    = var.server_location
  auto_delete = false
  labels      = local.common_labels
}

resource "hcloud_firewall" "server" {
  name   = "${local.resource_prefix}-firewall"
  labels = local.common_labels

  rule {
    description = "SSH administration from trusted networks"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = var.ssh_allowed_cidrs
  }

  rule {
    description = "HTTP for HTTPS certificate issuance and redirect"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "HTTP/3"
    direction   = "in"
    protocol    = "udp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }

  rule {
    description = "ICMP and ICMPv6"
    direction   = "in"
    protocol    = "icmp"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_server" "this" {
  name        = var.server_name
  server_type = var.server_type
  image       = var.server_image
  location    = var.server_location
  ssh_keys    = [hcloud_ssh_key.deployment.id]
  backups     = var.enable_backups
  labels      = local.common_labels

  firewall_ids = [hcloud_firewall.server.id]

  delete_protection  = var.protect_server
  rebuild_protection = var.protect_server

  public_net {
    ipv4_enabled = true
    ipv4         = hcloud_primary_ip.ipv4.id
    ipv6_enabled = true
    ipv6         = hcloud_primary_ip.ipv6.id
  }

  user_data = templatefile("${path.module}/templates/cloud-init.yaml.tftpl", {
    deployment_user      = var.deployment_user
    deployment_directory = var.deployment_directory
    ssh_public_key       = trimspace(var.ssh_public_key)
    application_domain   = var.application_domain
    oidc_domain          = var.oidc_domain
    code_repository_url  = var.code_repository_url
    code_repository_ref  = var.code_repository_ref
  })
}

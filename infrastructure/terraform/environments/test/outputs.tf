output "server_id" {
  description = "Hetzner Cloud test server identifier."
  value       = module.host.server_id
}

output "server_ipv4" {
  description = "Stable public IPv4 address for both test DNS records."
  value       = module.host.server_ipv4
}

output "server_ipv6_network" {
  description = "Public IPv6 network assigned to the test server."
  value       = module.host.server_ipv6_network
}

output "server_ipv6" {
  description = "Public IPv6 address assigned to the test server."
  value       = module.host.server_ipv6
}

output "application_url" {
  description = "Configured public CRM test URL."
  value       = "https://${var.application_domain}"
}

output "oidc_url" {
  description = "Configured public fake OIDC URL."
  value       = "https://${var.oidc_domain}"
}

output "ssh_command" {
  description = "Command for connecting as the deployment user."
  value       = "ssh ${var.deployment_user}@${module.host.server_ipv4}"
}

output "required_ipv4_dns_records" {
  description = "Bluehost DNS A records for the test environment."
  value = {
    (var.application_domain) = module.host.server_ipv4
    (var.oidc_domain)        = module.host.server_ipv4
  }
}

output "required_ipv6_dns_records" {
  description = "Optional Bluehost DNS AAAA records for the test environment."
  value = {
    (var.application_domain) = module.host.server_ipv6
    (var.oidc_domain)        = module.host.server_ipv6
  }
}

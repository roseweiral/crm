output "server_id" {
  description = "Hetzner Cloud server identifier."
  value       = hcloud_server.this.id
}

output "server_ipv4" {
  description = "Stable public IPv4 address."
  value       = hcloud_primary_ip.ipv4.ip_address
}

output "server_ipv6_network" {
  description = "Public IPv6 network assigned to the server."
  value       = hcloud_primary_ip.ipv6.ip_network
}

output "server_ipv6" {
  description = "Public IPv6 address assigned to the server."
  value       = hcloud_server.this.ipv6_address
}

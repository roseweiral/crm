module "host" {
  source = "../../modules/hetzner-host"

  project_name    = "volunteer-crm"
  environment     = "test"
  server_name     = var.server_name
  server_type     = var.server_type
  server_image    = var.server_image
  server_location = var.server_location

  enable_backups = var.enable_backups
  protect_server = var.protect_server

  ssh_public_key    = var.ssh_public_key
  ssh_allowed_cidrs = var.ssh_allowed_cidrs

  deployment_user      = var.deployment_user
  deployment_directory = var.deployment_directory
}

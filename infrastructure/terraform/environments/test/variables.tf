variable "server_name" {
  description = "Hostname assigned to the Hetzner test server."
  type        = string
  default     = "volunteer-crm-test"
}

variable "server_type" {
  description = "Hetzner server type; CX23 provides 2 shared vCPUs and 4 GB RAM."
  type        = string
  default     = "cx23"
}

variable "server_location" {
  description = "Hetzner location code."
  type        = string
  default     = "nbg1"
}

variable "server_image" {
  description = "Hetzner operating-system image."
  type        = string
  default     = "ubuntu-24.04"
}

variable "enable_backups" {
  description = "Enable Hetzner backups for the test server."
  type        = bool
  default     = false
}

variable "protect_server" {
  description = "Protect the test server from accidental deletion and rebuild."
  type        = bool
  default     = false
}

variable "ssh_public_key" {
  description = "SSH public key injected through TF_VAR_ssh_public_key."
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "Trusted SSH source CIDRs injected through TF_VAR_ssh_allowed_cidrs."
  type        = list(string)

  validation {
    condition     = length(var.ssh_allowed_cidrs) > 0
    error_message = "At least one trusted SSH source CIDR must be supplied."
  }
}

variable "deployment_user" {
  description = "Non-root operating-system account used for deployments."
  type        = string
  default     = "deploy"
}

variable "deployment_directory" {
  description = "Absolute directory in which test application code is deployed."
  type        = string
  default     = "/opt/volunteer-crm"
}

variable "application_domain" {
  description = "Public DNS hostname for the CRM test application."
  type        = string
  default     = "crm-test.roseweir.com"
}

variable "oidc_domain" {
  description = "Public DNS hostname for the test fake OIDC provider."
  type        = string
  default     = "login.crm-test.roseweir.com"
}

variable "code_repository_url" {
  description = "Git repository used by the test deployment step."
  type        = string
  default     = "https://github.com/roseweiral/crm.git"
}

variable "code_repository_ref" {
  description = "Git branch, tag, or commit deployed to test."
  type        = string
  default     = "Infra-Test"
}

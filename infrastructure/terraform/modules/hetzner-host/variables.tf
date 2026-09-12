variable "project_name" {
  description = "Short name used for Hetzner resource names and labels."
  type        = string
}

variable "environment" {
  description = "Deployment environment name used for resource names and labels."
  type        = string
}

variable "server_name" {
  description = "Hostname assigned to the Hetzner server."
  type        = string
}

variable "server_type" {
  description = "Hetzner server type."
  type        = string
}

variable "server_location" {
  description = "Hetzner location code, such as nbg1, fsn1, or hel1."
  type        = string
}

variable "server_image" {
  description = "Hetzner operating-system image."
  type        = string
}

variable "enable_backups" {
  description = "Enable Hetzner server backups."
  type        = bool
}

variable "protect_server" {
  description = "Protect the server from accidental deletion and rebuild."
  type        = bool
}

variable "ssh_public_key" {
  description = "SSH public key installed for server administration."
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "IPv4 or IPv6 CIDRs permitted to connect over SSH."
  type        = list(string)

  validation {
    condition     = length(var.ssh_allowed_cidrs) > 0
    error_message = "At least one trusted SSH source CIDR must be supplied."
  }
}

variable "deployment_user" {
  description = "Non-root operating-system account used for deployments."
  type        = string

  validation {
    condition     = can(regex("^[a-z_][a-z0-9_-]{0,30}$", var.deployment_user))
    error_message = "The deployment user must be a valid Linux username."
  }
}

variable "deployment_directory" {
  description = "Absolute directory in which application code will be deployed."
  type        = string

  validation {
    condition     = startswith(var.deployment_directory, "/")
    error_message = "The deployment directory must be an absolute path."
  }
}

variable "application_domain" {
  description = "Public DNS hostname for the application."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", var.application_domain))
    error_message = "Supply a lower-case DNS hostname without a scheme or path."
  }
}

variable "oidc_domain" {
  description = "Public DNS hostname for the environment's OIDC provider."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$", var.oidc_domain))
    error_message = "Supply a lower-case DNS hostname without a scheme or path."
  }
}

variable "code_repository_url" {
  description = "Git repository used by the application deployment step."
  type        = string
}

variable "code_repository_ref" {
  description = "Git branch, tag, or commit deployed to the environment."
  type        = string
}

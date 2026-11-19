variable "atlas_org_id" {
  description = "MongoDB Atlas organization ID."
  type        = string
}

variable "project_name" {
  description = "Name of the dedicated Atlas training project."
  type        = string
  default     = "MongoDB Exercise 13"
}

variable "cluster_name" {
  description = "Name of the M0 free-tier cluster."
  type        = string
  default     = "exercise13-free"
}

variable "atlas_database_username" {
  description = "Atlas database user name."
  type        = string
  default     = "lab13_user"
}

variable "atlas_user_password" {
  description = "Secret password for the Atlas database user."
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.atlas_user_password) >= 16
    error_message = "Use an Atlas database password at least 16 characters long."
  }
}

variable "atlas_database_name" {
  description = "Database the Atlas user can access."
  type        = string
  default     = "lab13"
}

variable "allowed_cidr" {
  description = "Your client IP address as a narrow CIDR (for example 203.0.113.12/32); 0.0.0.0/0 is rejected."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_cidr)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "Provide a valid, restricted IPv4 CIDR; unrestricted 0.0.0.0/0 is not allowed."
  }
}

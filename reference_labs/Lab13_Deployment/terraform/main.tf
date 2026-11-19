terraform {
  required_version = ">= 1.5.0"
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.16"
    }
  }
}

provider "mongodbatlas" {}

resource "mongodbatlas_project" "lab13" {
  name   = var.project_name
  org_id = var.atlas_org_id
}

resource "mongodbatlas_cluster" "lab13" {
  project_id                   = mongodbatlas_project.lab13.id
  name                         = var.cluster_name
  cluster_type                 = "REPLICASET"
  provider_name                = "AWS"
  provider_region_name         = "AP_SOUTH_1"
  provider_instance_size_name  = "M0"
  mongo_db_major_version       = "8.0"
  auto_scaling_disk_gb_enabled = false
}

resource "mongodbatlas_database_user" "lab13" {
  project_id         = mongodbatlas_project.lab13.id
  username           = var.atlas_database_username
  password           = var.atlas_user_password
  auth_database_name = "admin"

  roles {
    role_name     = "readWrite"
    database_name = var.atlas_database_name
  }
}

resource "mongodbatlas_project_ip_access_list" "lab13" {
  project_id = mongodbatlas_project.lab13.id
  cidr_block = var.allowed_cidr
  comment    = "Explicitly scoped lab client CIDR; never open to all IPs."
}

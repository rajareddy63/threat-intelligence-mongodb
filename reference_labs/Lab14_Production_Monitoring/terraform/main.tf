terraform {
  required_version = ">= 1.6.0"

  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.20"
    }
  }
}

provider "mongodbatlas" {
  public_key  = var.public_key
  private_key = var.private_key
}

variable "public_key" {
  type      = string
  sensitive = true
}

variable "private_key" {
  type      = string
  sensitive = true
}

resource "mongodbatlas_project" "lab14" {
  name = "lab14-production"
}

resource "mongodbatlas_cluster" "primary" {
  project_id = mongodbatlas_project.lab14.id
  name       = "lab14-prod-cluster"
  provider_name = "TENANT"
  backing_provider_name = "AWS"
  provider_region_name = "US_EAST_1"
  provider_instance_size_name = "M0"
}

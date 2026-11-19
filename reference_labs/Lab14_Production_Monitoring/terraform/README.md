# Terraform skeleton

This directory contains a minimal Atlas provisioning configuration for a MongoDB production-like environment.

## Example usage

```hcl
provider "mongodbatlas" {
  public_key  = var.public_key
  private_key = var.private_key
}
```

Replace the placeholders with real Atlas values before planning or applying.

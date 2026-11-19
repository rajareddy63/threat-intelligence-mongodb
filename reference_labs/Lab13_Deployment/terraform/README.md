# MongoDB Atlas Terraform (prepared, not applied)

`main.tf` follows the professor's Atlas project/M0/user reference while replacing its unrestricted `0.0.0.0/0` rule with an explicit, validated CIDR. The database user has read/write permissions only on `lab13`. No Atlas credentials or real password are stored in the repository.

The configuration passed `terraform fmt -check`, `terraform init -backend=false`, and `terraform validate` with Terraform 1.9.8 and MongoDB Atlas provider 1.41.2. The provider lockfile is included. No `terraform plan` or `apply` was run, and no Atlas resources were created.

When Terraform is installed and you have independently configured Atlas API keys in the shell, copy `terraform.tfvars.example` to the ignored `terraform.tfvars`, supply your organization ID and actual client `/32` CIDR, and set `TF_VAR_atlas_user_password` in your private shell environment. Review the plan before applying:

```powershell
terraform init
terraform validate
terraform plan
# Creating cloud resources requires explicit user approval; do not apply without it.
```

Atlas API credentials can be supplied as `MONGODB_ATLAS_PUBLIC_KEY` and `MONGODB_ATLAS_PRIVATE_KEY` environment variables. Never commit either key, a real password, tfstate, or a plan. The configuration has not been applied and creates no cloud resources.

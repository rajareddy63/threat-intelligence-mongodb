output "cluster_srv_record" {
  description = "Atlas SRV connection hostname, without credentials."
  value       = mongodbatlas_cluster.lab13.connection_strings[0].standard_srv
}

output "connection_uri_template" {
  description = "SRV URI template; substitute credentials outside Terraform output/state."
  value       = "mongodb+srv://${var.atlas_database_username}:<PASSWORD>@${trimprefix(mongodbatlas_cluster.lab13.connection_strings[0].standard_srv, "mongodb+srv://")}/${var.atlas_database_name}?retryWrites=true&w=majority"
}

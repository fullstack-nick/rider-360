output "artifact_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "data_bucket" {
  value = google_storage_bucket.data.name
}

output "cloud_sql_instance" {
  value = google_sql_database_instance.postgres.name
}

output "cloud_sql_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}

output "metabase_db_user" {
  value = local.metabase_db_user
}

output "dagster_db_user" {
  value = local.dagster_db_user
}

output "metabase_admin_secret" {
  value = google_secret_manager_secret.metabase_admin.secret_id
}

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  value = google_service_account.deployer.email
}

output "metabase_url" {
  value = try(google_cloud_run_v2_service.metabase[0].uri, null)
}

output "dagster_public_url" {
  value = try(google_cloud_run_v2_service.dagster_web["public"].uri, null)
}

output "dagster_admin_url" {
  value = try(google_cloud_run_v2_service.dagster_web["admin"].uri, null)
}

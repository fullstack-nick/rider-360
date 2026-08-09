data "google_project" "host" {
  project_id = var.project_id
}

locals {
  labels = {
    application         = "rider-360"
    environment         = var.environment
    managed_by          = "terraform"
    data_classification = "synthetic"
  }
  dataset_ids = toset([
    "r360_raw",
    "r360_staging",
    "r360_intermediate",
    "r360_marts",
    "r360_audit",
  ])
  metabase_db_user = trimsuffix(google_service_account.metabase.email, ".gserviceaccount.com")
  dagster_db_user  = trimsuffix(google_service_account.dagster.email, ".gserviceaccount.com")
  dagster_db_url   = "postgresql://${urlencode(local.dagster_db_user)}@127.0.0.1:5432/r360_dagster"
  bi_db_url        = "postgresql://${urlencode(local.dagster_db_user)}@127.0.0.1:5432/r360_bi"
  marketing_arrival_uri = (
    "gs://${google_storage_bucket.data.name}/arrivals/marketing/latest.json"
  )
}

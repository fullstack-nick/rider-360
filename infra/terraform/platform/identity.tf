resource "google_service_account" "metabase" {
  project      = var.project_id
  account_id   = "r360-metabase"
  display_name = "Rider 360 Metabase"
  description  = "Cloud Run identity with Cloud SQL access only; no BigQuery permission."
}

resource "google_service_account" "dagster" {
  project      = var.project_id
  account_id   = "r360-dagster"
  display_name = "Rider 360 Dagster"
  description  = "Orchestration, BigQuery transformation, GCS, and BI publication identity."
}

resource "google_service_account" "deployer" {
  project      = var.project_id
  account_id   = "r360-deployer"
  display_name = "Rider 360 GitHub deployer"
  description  = "Keyless GitHub Actions runtime deployer."
}

locals {
  metabase_project_roles = toset([
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
  ])
  dagster_project_roles = toset([
    "roles/bigquery.jobUser",
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  deployer_project_roles = toset([
    "roles/artifactregistry.writer",
    "roles/run.admin",
  ])
}

resource "google_project_iam_member" "metabase" {
  for_each = local.metabase_project_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.metabase.email}"
}

resource "google_project_iam_member" "dagster" {
  for_each = local.dagster_project_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.dagster.email}"
}

resource "google_project_iam_custom_role" "dagster_job_reader" {
  project     = var.project_id
  role_id     = "r360BigQueryJobReader"
  title       = "Rider 360 BigQuery job reader"
  description = "Allows the Rider orchestrator to query only its own JOBS_BY_USER telemetry."
  permissions = ["bigquery.jobs.list"]
  stage       = "GA"
}

resource "google_project_iam_member" "dagster_job_reader" {
  project = var.project_id
  role    = google_project_iam_custom_role.dagster_job_reader.id
  member  = "serviceAccount:${google_service_account.dagster.email}"
}

resource "google_project_iam_member" "deployer" {
  for_each = local.deployer_project_roles
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_bigquery_dataset_iam_member" "dagster_editor" {
  for_each   = google_bigquery_dataset.layers
  project    = var.project_id
  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dagster.email}"
}

resource "google_storage_bucket_iam_member" "dagster_objects" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dagster.email}"
}

resource "google_storage_bucket_iam_member" "dagster_bucket_metadata" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.dagster.email}"
}

resource "google_service_account_iam_member" "deployer_uses_metabase" {
  service_account_id = google_service_account.metabase.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_uses_dagster" {
  service_account_id = google_service_account.dagster.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "r360-github"
  display_name              = "Rider 360 GitHub"
  description               = "Keyless deployments from the public Rider 360 repository."
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "r360-github-oidc"
  display_name                       = "Rider 360 GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == 'refs/heads/main'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

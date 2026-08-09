resource "random_password" "metabase_admin" {
  length           = 32
  special          = true
  override_special = "!#$%&*+-=?@_"
  min_lower        = 6
  min_upper        = 4
  min_numeric      = 4
  min_special      = 4
}

resource "random_password" "metabase_encryption" {
  length  = 64
  special = false
}

resource "google_secret_manager_secret" "metabase_admin" {
  project   = var.project_id
  secret_id = "r360-metabase-admin-password"
  labels    = merge(local.labels, { component = "metabase" })

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "metabase_admin" {
  secret      = google_secret_manager_secret.metabase_admin.id
  secret_data = random_password.metabase_admin.result
}

resource "google_secret_manager_secret" "metabase_encryption" {
  project   = var.project_id
  secret_id = "r360-metabase-encryption-key"
  labels    = merge(local.labels, { component = "metabase" })

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "metabase_encryption" {
  secret      = google_secret_manager_secret.metabase_encryption.id
  secret_data = random_password.metabase_encryption.result
}

resource "google_secret_manager_secret_iam_member" "metabase_encryption" {
  secret_id = google_secret_manager_secret.metabase_encryption.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.metabase.email}"
}

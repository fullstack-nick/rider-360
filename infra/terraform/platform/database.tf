resource "google_sql_database_instance" "postgres" {
  project             = var.project_id
  name                = "r360-pg-${var.environment}"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true

  settings {
    edition                     = "ENTERPRISE"
    tier                        = "db-custom-1-3840"
    availability_type           = "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = 20
    disk_autoresize             = true
    deletion_protection_enabled = true
    user_labels                 = merge(local.labels, { component = "postgres" })

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "01:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7
      hour         = 2
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_plans_per_minute  = 5
      query_string_length     = 1024
      record_application_tags = true
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "metabase" {
  project  = var.project_id
  name     = "r360_metabase"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_database" "dagster" {
  project  = var.project_id
  name     = "r360_dagster"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_database" "bi" {
  project  = var.project_id
  name     = "r360_bi"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "metabase_iam" {
  project         = var.project_id
  name            = local.metabase_db_user
  instance        = google_sql_database_instance.postgres.name
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
  deletion_policy = "ABANDON"
}

resource "google_sql_user" "dagster_iam" {
  project         = var.project_id
  name            = local.dagster_db_user
  instance        = google_sql_database_instance.postgres.name
  type            = "CLOUD_IAM_SERVICE_ACCOUNT"
  deletion_policy = "ABANDON"
}

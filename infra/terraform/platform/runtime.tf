locals {
  dagster_web_services = var.deploy_runtime ? {
    public = {
      name          = "r360-dagster-public"
      read_only_arg = ["--read-only"]
      min_instances = 1
    }
    admin = {
      name          = "r360-dagster-admin"
      read_only_arg = []
      min_instances = 0
    }
  } : {}

  proxy_args = [
    "--auto-iam-authn",
    "--lazy-refresh",
    "--address=0.0.0.0",
    "--port=5432",
    "--health-check",
    "--http-address=0.0.0.0",
    "--http-port=9801",
    google_sql_database_instance.postgres.connection_name,
  ]
}

resource "google_cloud_run_v2_service" "metabase" {
  count = var.deploy_runtime ? 1 : 0

  project             = var.project_id
  name                = "r360-metabase"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = merge(local.labels, { component = "metabase" })

  template {
    service_account                  = google_service_account.metabase.email
    timeout                          = "300s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

    containers {
      name       = "metabase"
      image      = var.metabase_image
      depends_on = ["cloud-sql-proxy"]

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "MB_JETTY_PORT"
        value = "8080"
      }
      env {
        name  = "MB_DB_TYPE"
        value = "postgres"
      }
      env {
        name  = "MB_DB_HOST"
        value = "127.0.0.1"
      }
      env {
        name  = "MB_DB_PORT"
        value = "5432"
      }
      env {
        name  = "MB_DB_DBNAME"
        value = google_sql_database.metabase.name
      }
      env {
        name  = "MB_DB_USER"
        value = local.metabase_db_user
      }
      env {
        name  = "MB_DB_PASS"
        value = ""
      }
      env {
        name  = "MB_SITE_NAME"
        value = "Rider 360"
      }
      env {
        name  = "MB_ANON_TRACKING_ENABLED"
        value = "false"
      }
      env {
        name  = "JAVA_TIMEZONE"
        value = "Europe/Vienna"
      }
      env {
        name = "MB_ENCRYPTION_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.metabase_encryption.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        initial_delay_seconds = 5
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 60
        http_get {
          path = "/api/health"
          port = 8080
        }
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = var.cloud_sql_proxy_image
      args  = local.proxy_args

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 2
        period_seconds        = 2
        failure_threshold     = 30
        http_get {
          path = "/startup"
          port = 9801
        }
      }
    }
  }

  depends_on = [
    google_sql_user.metabase_iam,
    google_secret_manager_secret_iam_member.metabase_encryption,
  ]
}

resource "google_cloud_run_v2_service" "dagster_web" {
  for_each = local.dagster_web_services

  project             = var.project_id
  name                = each.value.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false
  labels              = merge(local.labels, { component = "dagster-${each.key}" })

  template {
    service_account                  = google_service_account.dagster.email
    timeout                          = "300s"
    max_instance_request_concurrency = 20

    scaling {
      min_instance_count = each.value.min_instances
      max_instance_count = 1
    }

    containers {
      name       = "dagster-webserver"
      image      = var.rider_image
      command    = ["dagster-webserver"]
      args       = concat(each.value.read_only_arg, ["--host", "0.0.0.0", "--port", "8080", "--grpc-host", "127.0.0.1", "--grpc-port", "4000"])
      depends_on = ["cloud-sql-proxy", "dagster-code"]

      ports {
        name           = "http1"
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "DAGSTER_HOME"
        value = "/opt/dagster/dagster_cloud"
      }
      env {
        name  = "DAGSTER_POSTGRES_URL"
        value = local.dagster_db_url
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "R360_MARKETING_ARRIVAL_URI"
        value = local.marketing_arrival_uri
      }
      env {
        name  = "R360_DATA_BUCKET"
        value = google_storage_bucket.data.name
      }
      env {
        name  = "R360_BI_PG_DSN"
        value = local.bi_db_url
      }
      env {
        name  = "R360_BI_READER_ROLE"
        value = local.metabase_db_user
      }

      startup_probe {
        initial_delay_seconds = 3
        timeout_seconds       = 5
        period_seconds        = 5
        failure_threshold     = 30
        http_get {
          path = "/server_info"
          port = 8080
        }
      }
    }

    containers {
      name    = "dagster-code"
      image   = var.rider_image
      command = ["dagster"]
      args    = ["code-server", "start", "--host", "0.0.0.0", "--port", "4000", "--module-name", "rider360.orchestration.definitions"]

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "R360_MARKETING_ARRIVAL_URI"
        value = local.marketing_arrival_uri
      }

      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 2
        period_seconds        = 2
        failure_threshold     = 30
        tcp_socket {
          port = 4000
        }
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = var.cloud_sql_proxy_image
      args  = local.proxy_args

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 2
        period_seconds        = 2
        failure_threshold     = 30
        http_get {
          path = "/startup"
          port = 9801
        }
      }
    }
  }

  depends_on = [google_sql_user.dagster_iam]

  # Terraform owns the service topology; the keyless release workflow owns the
  # two application-container revisions after the initial digest-pinned create.
  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[1].image,
    ]
  }
}

resource "google_cloud_run_v2_worker_pool" "dagster_daemon" {
  count = var.deploy_runtime ? 1 : 0

  project             = var.project_id
  name                = "r360-dagster-daemon"
  location            = var.region
  launch_stage        = "GA"
  deletion_protection = false
  labels              = merge(local.labels, { component = "dagster-daemon" })
  scaling {
    manual_instance_count = 1
  }

  template {
    service_account = google_service_account.dagster.email

    containers {
      name       = "dagster-daemon"
      image      = var.rider_image
      command    = ["dagster-daemon"]
      args       = ["run", "--grpc-host", "127.0.0.1", "--grpc-port", "4000"]
      depends_on = ["cloud-sql-proxy", "dagster-code"]

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      env {
        name  = "DAGSTER_HOME"
        value = "/opt/dagster/dagster_cloud"
      }
      env {
        name  = "DAGSTER_POSTGRES_URL"
        value = local.dagster_db_url
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "R360_MARKETING_ARRIVAL_URI"
        value = local.marketing_arrival_uri
      }
      env {
        name  = "R360_DATA_BUCKET"
        value = google_storage_bucket.data.name
      }
      env {
        name  = "R360_GENERATION_PROFILE"
        value = "full"
      }
      env {
        name  = "R360_DATASET_DIR"
        value = "/tmp/rider360/full"
      }
      env {
        name  = "R360_BI_PG_DSN"
        value = local.bi_db_url
      }
      env {
        name  = "R360_BI_READER_ROLE"
        value = local.metabase_db_user
      }
    }

    containers {
      name    = "dagster-code"
      image   = var.rider_image
      command = ["dagster"]
      args    = ["code-server", "start", "--host", "0.0.0.0", "--port", "4000", "--module-name", "rider360.orchestration.definitions"]

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      env {
        name  = "DAGSTER_HOME"
        value = "/opt/dagster/dagster_cloud"
      }
      env {
        name  = "DAGSTER_POSTGRES_URL"
        value = local.dagster_db_url
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "R360_DATA_BUCKET"
        value = google_storage_bucket.data.name
      }
      env {
        name  = "R360_MARKETING_ARRIVAL_URI"
        value = local.marketing_arrival_uri
      }
      env {
        name  = "R360_GENERATION_PROFILE"
        value = "full"
      }
      env {
        name  = "R360_DATASET_DIR"
        value = "/tmp/rider360/full"
      }
      env {
        name  = "R360_BI_PG_DSN"
        value = local.bi_db_url
      }
      env {
        name  = "R360_BI_READER_ROLE"
        value = local.metabase_db_user
      }

      startup_probe {
        initial_delay_seconds = 2
        timeout_seconds       = 2
        period_seconds        = 2
        failure_threshold     = 30
        tcp_socket {
          port = 4000
        }
      }
    }

    containers {
      name  = "cloud-sql-proxy"
      image = var.cloud_sql_proxy_image
      args  = local.proxy_args

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }

      startup_probe {
        initial_delay_seconds = 1
        timeout_seconds       = 2
        period_seconds        = 2
        failure_threshold     = 30
        http_get {
          path = "/startup"
          port = 9801
        }
      }
    }
  }

  depends_on = [google_sql_user.dagster_iam]

  # See the Cloud Run service lifecycle note above. Proxy/config changes remain
  # Terraform-managed; only application image digests are release-managed.
  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[1].image,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "metabase_public" {
  count = var.deploy_runtime ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.metabase[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "dagster_public" {
  count = var.deploy_runtime ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.dagster_web["public"].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "dagster_admin" {
  count = var.deploy_runtime && var.admin_invoker != "" ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.dagster_web["admin"].name
  role     = "roles/run.invoker"
  member   = var.admin_invoker
}

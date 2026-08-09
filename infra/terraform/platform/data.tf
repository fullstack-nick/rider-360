resource "google_bigquery_dataset" "layers" {
  for_each = local.dataset_ids

  project                    = var.project_id
  dataset_id                 = each.value
  friendly_name              = "Rider 360 ${trimprefix(each.value, "r360_")}"
  description                = "Rider 360 fictional synthetic analytics ${trimprefix(each.value, "r360_")} layer."
  location                   = var.bigquery_location
  delete_contents_on_destroy = false
  max_time_travel_hours      = 168
  labels                     = merge(local.labels, { component = "bigquery" })

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_storage_bucket" "data" {
  name                        = "r360-data-${data.google_project.host.number}"
  project                     = var.project_id
  location                    = var.bigquery_location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = merge(local.labels, { component = "data" })

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_artifact_registry_repository" "containers" {
  project       = var.project_id
  location      = var.region
  repository_id = "r360-containers"
  description   = "Digest-pinned Rider 360 application images."
  format        = "DOCKER"
  labels        = merge(local.labels, { component = "containers" })

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }
}

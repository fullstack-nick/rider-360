variable "project_id" {
  description = "Approved billed GCP host project."
  type        = string

  validation {
    condition     = var.project_id == "tracegate-r7m5o9ld"
    error_message = "This state is deliberately pinned to the approved TraceGate incubator."
  }
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "bigquery_location" {
  type    = string
  default = "EU"
}

variable "environment" {
  type    = string
  default = "demo"
}

variable "github_repository" {
  type    = string
  default = "fullstack-nick/rider-360"
}

variable "admin_invoker" {
  description = "Optional IAM member allowed to invoke the private Dagster admin service."
  type        = string
  default     = ""
}

variable "billing_account_id" {
  description = "Optional billing account resource name or ID for alerts-only budget telemetry."
  type        = string
  default     = ""
  sensitive   = true
}

variable "budget_amount_units" {
  type    = number
  default = 10000
}

variable "budget_currency_code" {
  description = "Currency associated with the approved billing account."
  type        = string
  default     = "TRY"

  validation {
    condition     = can(regex("^[A-Z]{3}$", var.budget_currency_code))
    error_message = "budget_currency_code must be a three-letter ISO currency code."
  }
}

variable "deploy_runtime" {
  description = "Create Cloud Run services and worker pool after the Rider image exists."
  type        = bool
  default     = false
}

variable "rider_image" {
  description = "Immutable Artifact Registry Rider 360 image reference."
  type        = string
  default     = ""

  validation {
    condition     = !var.deploy_runtime || startswith(var.rider_image, "europe-west1-docker.pkg.dev/tracegate-r7m5o9ld/r360-containers/rider-360@sha256:")
    error_message = "Runtime deployment requires a digest-pinned Rider image from r360-containers."
  }
}

variable "metabase_image" {
  type    = string
  default = "metabase/metabase:v0.61.2"
}

variable "cloud_sql_proxy_image" {
  type    = string
  default = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.22.0"
}

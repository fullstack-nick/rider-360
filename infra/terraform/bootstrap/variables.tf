variable "project_id" {
  description = "Approved billed GCP host project."
  type        = string

  validation {
    condition     = var.project_id == "tracegate-r7m5o9ld"
    error_message = "Bootstrap is deliberately pinned to the approved TraceGate incubator."
  }
}

variable "region" {
  type    = string
  default = "europe-west1"
}

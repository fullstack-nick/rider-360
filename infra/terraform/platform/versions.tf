terraform {
  required_version = ">= 1.10, < 2.0"

  backend "gcs" {
    bucket = "r360-tfstate-555370648578"
    prefix = "rider-360/demo/platform"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.22"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

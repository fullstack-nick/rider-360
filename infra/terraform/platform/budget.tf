resource "google_billing_budget" "alerts_only" {
  count = var.billing_account_id == "" ? 0 : 1

  # The provider expects the bare six-character-group ID and constructs the
  # billingAccounts/<id> API parent itself.
  billing_account = trimprefix(var.billing_account_id, "billingAccounts/")
  display_name    = "Rider 360 demo alerts only"

  budget_filter {
    projects = ["projects/${data.google_project.host.number}"]
  }

  amount {
    specified_amount {
      currency_code = var.budget_currency_code
      units         = tostring(var.budget_amount_units)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

}

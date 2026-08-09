param(
    [string]$InventoryPath = "artifacts/gcp/tracegate-after.json"
)

$ErrorActionPreference = "Stop"
$resolved = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $InventoryPath))
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
    throw "Inventory not found: $resolved"
}
$inventory = Get-Content -Raw -LiteralPath $resolved | ConvertFrom-Json

function Assert-ExactNames {
    param(
        [string]$Label,
        [object[]]$Items,
        [string[]]$Expected
    )
    $actual = @($Items | ForEach-Object { $_.name } | Sort-Object)
    $expectedSorted = @($Expected | Sort-Object)
    if (Compare-Object -ReferenceObject $expectedSorted -DifferenceObject $actual) {
        throw "$Label changed. Expected [$($expectedSorted -join ', ')], got [$($actual -join ', ')]."
    }
}

Assert-ExactNames "Compute instances" @($inventory.compute_instances) @("tracegate-vm")
Assert-ExactNames "Compute disks" @($inventory.compute_disks) @("tracegate-vm")
Assert-ExactNames "Networks" @($inventory.networks) @("default")
Assert-ExactNames "Firewall rules" @($inventory.firewall_rules) @(
    "default-allow-icmp",
    "default-allow-internal",
    "default-allow-rdp",
    "default-allow-ssh",
    "tracegate-v0-1-http",
    "tracegate-v0-1-ssh"
)

$resourceChecks = @(
    @{ Label = "BigQuery dataset"; Names = @($inventory.bigquery_datasets | ForEach-Object { $_.datasetReference.datasetId }); Prefix = "r360_" },
    @{ Label = "Storage bucket"; Names = @($inventory.storage_buckets | ForEach-Object { $_.name }); Prefix = "r360-" },
    @{ Label = "Cloud Run service"; Names = @($inventory.cloud_run_services | ForEach-Object { $_.metadata.name }); Prefix = "r360-" },
    @{ Label = "Cloud Run worker pool"; Names = @($inventory.cloud_run_worker_pools | ForEach-Object { $_.metadata.name }); Prefix = "r360-" },
    @{ Label = "Cloud SQL instance"; Names = @($inventory.cloud_sql_instances | ForEach-Object { $_.name }); Prefix = "r360-" },
    @{ Label = "Artifact repository"; Names = @($inventory.artifact_repositories | ForEach-Object { ($_.name -split '/')[-1] }); Prefix = "r360-" },
    @{ Label = "Secret"; Names = @($inventory.secrets | ForEach-Object { ($_.name -split '/')[-1] }); Prefix = "r360-" }
)
foreach ($check in $resourceChecks) {
    $unexpected = @($check.Names | Where-Object { $_ -and -not $_.StartsWith($check.Prefix) })
    if ($unexpected) {
        throw "$($check.Label) containment failed: $($unexpected -join ', ')"
    }
}

$allowedExistingAccounts = @(
    "555370648578-compute@developer.gserviceaccount.com",
    "tracegate-vm@tracegate-r7m5o9ld.iam.gserviceaccount.com"
)
$unexpectedAccounts = @(
    $inventory.service_accounts |
        ForEach-Object { $_.email } |
        Where-Object { $_ -notin $allowedExistingAccounts -and -not $_.StartsWith("r360-") }
)
if ($unexpectedAccounts) {
    throw "Unexpected non-Rider service accounts: $($unexpectedAccounts -join ', ')"
}

Write-Output "Containment verified: TraceGate compute/network/firewall baseline is intact and all added durable resources use the Rider 360 namespace."

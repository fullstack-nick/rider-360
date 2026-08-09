param(
    [string]$ProjectId = "tracegate-r7m5o9ld",
    [string]$OutputPath = "artifacts/gcp/tracegate-before.json"
)

$ErrorActionPreference = "Stop"
if ($ProjectId -ne "tracegate-r7m5o9ld") {
    throw "This inventory script is intentionally scoped to the approved TraceGate incubator."
}

function Invoke-GcloudJson {
    param([string[]]$Arguments)
    # Windows PowerShell can promote informational native stderr to a terminating
    # NativeCommandError when the script uses fail-closed error handling. Capture
    # it separately and make the process exit code authoritative.
    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $raw = & gcloud.cmd @Arguments --project $ProjectId --format=json 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }
    if ($exitCode -ne 0 -or -not $raw) {
        return
    }
    $parsed = $raw | ConvertFrom-Json
    # Windows PowerShell preserves a top-level JSON array as one nested Object[].
    # Emit its members explicitly so callers always receive a flat collection.
    foreach ($item in $parsed) {
        Write-Output $item
    }
}

$project = Invoke-GcloudJson @("projects", "describe", $ProjectId)
$billing = Invoke-GcloudJson @("billing", "projects", "describe", $ProjectId)
$bqRaw = & bq.cmd ls --format=json --project_id=$ProjectId 2>$null
$bqDatasets = if ($LASTEXITCODE -eq 0 -and $bqRaw) { @($bqRaw | ConvertFrom-Json) } else { @() }
$bqDatasets = @($bqDatasets | Where-Object { $_.datasetReference -or $_.id })
$storageBuckets = @(Invoke-GcloudJson @("storage", "buckets", "list"))
$storageBuckets = @($storageBuckets | Where-Object { $_.name })
$enabledServices = @(& gcloud.cmd services list --enabled --project $ProjectId --format="value(config.name)" 2>$null)
$runServices = if ($enabledServices -contains "run.googleapis.com") {
    @(Invoke-GcloudJson @("run", "services", "list", "--region=europe-west1"))
} else { @() }
$runServices = @($runServices | Where-Object { $_.metadata.name -or $_.name })
$runWorkerPools = if ($enabledServices -contains "run.googleapis.com") {
    @(Invoke-GcloudJson @("run", "worker-pools", "list", "--region=europe-west1"))
} else { @() }
$runWorkerPools = @($runWorkerPools | Where-Object { $_.metadata.name -or $_.name })
$sqlInstances = if ($enabledServices -contains "sqladmin.googleapis.com") {
    @(Invoke-GcloudJson @("sql", "instances", "list"))
} else { @() }
$sqlInstances = @($sqlInstances | Where-Object { $_.name })
$repositories = if ($enabledServices -contains "artifactregistry.googleapis.com") {
    @(Invoke-GcloudJson @("artifacts", "repositories", "list", "--location=europe-west1"))
} else { @() }
$repositories = @($repositories | Where-Object { $_.name })
$secrets = if ($enabledServices -contains "secretmanager.googleapis.com") {
    @(Invoke-GcloudJson @("secrets", "list"))
} else { @() }
$secrets = @($secrets | Where-Object { $_.name })

$inventory = [ordered]@{
    captured_at_utc = [DateTime]::UtcNow.ToString("o")
    project = [ordered]@{
        project_id = $project.projectId
        project_number = $project.projectNumber
        lifecycle_state = $project.lifecycleState
        billing_enabled = $billing.billingEnabled
    }
    compute_instances = @(Invoke-GcloudJson @("compute", "instances", "list"))
    compute_disks = @(Invoke-GcloudJson @("compute", "disks", "list"))
    networks = @(Invoke-GcloudJson @("compute", "networks", "list"))
    firewall_rules = @(Invoke-GcloudJson @("compute", "firewall-rules", "list"))
    service_accounts = @(Invoke-GcloudJson @("iam", "service-accounts", "list"))
    bigquery_datasets = $bqDatasets
    storage_buckets = $storageBuckets
    cloud_run_services = $runServices
    cloud_run_worker_pools = $runWorkerPools
    cloud_sql_instances = $sqlInstances
    artifact_repositories = $repositories
    secrets = $secrets
}

$resolved = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
$parent = Split-Path -Parent $resolved
[System.IO.Directory]::CreateDirectory($parent) | Out-Null
$inventory | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $resolved -Encoding utf8
Write-Output $resolved

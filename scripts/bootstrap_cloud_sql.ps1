param(
  [string]$ProjectId = "tracegate-r7m5o9ld",
  [string]$Instance = "r360-pg-demo",
  [int]$Port = 54321,
  [string]$ProxyVersion = "2.22.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$localDir = Join-Path $repoRoot ".local"
$proxyPath = Join-Path $localDir "cloud-sql-proxy-$ProxyVersion.exe"
$proxyStdout = Join-Path $localDir "cloud-sql-proxy-bootstrap.stdout.log"
$proxyStderr = Join-Path $localDir "cloud-sql-proxy-bootstrap.stderr.log"

function New-R360Password {
  $bytes = [byte[]]::new(48)
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $generator.GetBytes($bytes)
  } finally {
    $generator.Dispose()
  }
  return [Convert]::ToBase64String($bytes).Replace("/", "_").Replace("+", "-") + "!a9"
}

if (-not (Test-Path -LiteralPath $localDir -PathType Container)) {
  New-Item -ItemType Directory -Path $localDir | Out-Null
}
if (-not (Test-Path -LiteralPath $proxyPath -PathType Leaf)) {
  $proxyUrl = "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v$ProxyVersion/cloud-sql-proxy.x64.exe"
  Invoke-WebRequest -Uri $proxyUrl -OutFile $proxyPath
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
  $uvPackageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
  $uvExecutable = Get-ChildItem -LiteralPath $uvPackageRoot -Directory -Filter "astral-sh.uv_*" -ErrorAction Stop |
    ForEach-Object { Join-Path $_.FullName "uv.exe" } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
  if (-not $uvExecutable) { throw "uv.exe was not found." }
} else {
  $uvExecutable = $uvCommand.Source
}

$connectionName = (gcloud.cmd sql instances describe $Instance --project=$ProjectId --format="value(connectionName)").Trim()
if ($connectionName -notmatch "^[a-z0-9-]+:[a-z0-9-]+:[a-z0-9-]+$") {
  throw "Unexpected Cloud SQL connection name."
}
$dagsterRole = (terraform -chdir="$repoRoot\infra\terraform\platform" output -raw dagster_db_user).Trim()
$metabaseRole = (terraform -chdir="$repoRoot\infra\terraform\platform" output -raw metabase_db_user).Trim()
if ($dagsterRole -notmatch "^r360-dagster@[a-z0-9-]+\.iam$" -or $metabaseRole -notmatch "^r360-metabase@[a-z0-9-]+\.iam$") {
  throw "Unexpected IAM database role output."
}

$temporaryPassword = New-R360Password
$passwordWasSet = $false
$passwordWasRotated = $false
$proxyProcess = $null
$previousQuotaProject = $env:GOOGLE_CLOUD_QUOTA_PROJECT
try {
  $env:GOOGLE_CLOUD_QUOTA_PROJECT = $ProjectId
  gcloud.cmd sql users set-password postgres --instance=$Instance --project=$ProjectId --password=$temporaryPassword --quiet | Out-Null
  $passwordWasSet = $true
  $proxyProcess = Start-Process -FilePath $proxyPath -ArgumentList @(
    "--address", "127.0.0.1", "--port", "$Port", $connectionName
  ) -WindowStyle Hidden -PassThru -RedirectStandardOutput $proxyStdout -RedirectStandardError $proxyStderr

  $ready = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
      $client = [System.Net.Sockets.TcpClient]::new()
      $client.Connect("127.0.0.1", $Port)
      $client.Dispose()
      $ready = $true
      break
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  if (-not $ready) { throw "Cloud SQL Auth Proxy did not become ready." }

  $env:R360_BOOTSTRAP_PASSWORD = $temporaryPassword
  & $uvExecutable run python "$repoRoot\scripts\bootstrap_cloud_sql.py" --port $Port --dagster-role $dagsterRole --metabase-role $metabaseRole
  if ($LASTEXITCODE -ne 0) { throw "Database bootstrap failed." }

  $rotatedPassword = New-R360Password
  gcloud.cmd sql users set-password postgres --instance=$Instance --project=$ProjectId --password=$rotatedPassword --quiet | Out-Null
  $passwordWasRotated = $true
  Write-Output "Cloud SQL bootstrap completed; the transient postgres credential was rotated and discarded."
} finally {
  Remove-Item Env:R360_BOOTSTRAP_PASSWORD -ErrorAction SilentlyContinue
  if ($null -eq $previousQuotaProject) {
    Remove-Item Env:GOOGLE_CLOUD_QUOTA_PROJECT -ErrorAction SilentlyContinue
  } else {
    $env:GOOGLE_CLOUD_QUOTA_PROJECT = $previousQuotaProject
  }
  $temporaryPassword = $null
  if ($proxyProcess -and -not $proxyProcess.HasExited) {
    Stop-Process -Id $proxyProcess.Id -ErrorAction Stop
    $proxyProcess.WaitForExit()
  }
  if ($passwordWasSet -and -not $passwordWasRotated) {
    $emergencyRotation = New-R360Password
    gcloud.cmd sql users set-password postgres --instance=$Instance --project=$ProjectId --password=$emergencyRotation --quiet | Out-Null
    $emergencyRotation = $null
  }
}

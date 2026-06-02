# export_data.ps1
# Run from the project root before migrating to a new machine.
# Creates an export/ folder with the SQLite file and a Postgres dump.
#
# Usage:
#   .\export_data.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExportDir = Join-Path $PSScriptRoot "export"
$SqliteSrc  = Join-Path $PSScriptRoot "backend\data\food_db.sqlite"
$SqliteDst  = Join-Path $ExportDir   "food_db.sqlite"
$PgDump     = Join-Path $ExportDir   "postgres_dump.sql"

Write-Host ""
Write-Host "=== DietSearch — export_data.ps1 ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Docker is running ────────────────────────────────────────────────
Write-Host "Checking Docker..." -NoNewline
try {
    docker info 2>&1 | Out-Null
    Write-Host " OK" -ForegroundColor Green
} catch {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "Docker is not running. Start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# ── 2. Check Postgres container is up ─────────────────────────────────────────
Write-Host "Checking Postgres container..." -NoNewline
$pgStatus = docker compose ps --status running --format json 2>$null | ConvertFrom-Json | Where-Object { $_.Service -eq "postgres" }
if (-not $pgStatus) {
    Write-Host " not running" -ForegroundColor Yellow
    Write-Host "Starting services..." -ForegroundColor Yellow
    docker compose up -d postgres
    Write-Host "Waiting for Postgres to be ready..."
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        $check = docker compose exec -T postgres pg_isready -U dietsearch 2>&1
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep 2
    }
    if (-not $ready) {
        Write-Host "Postgres did not become ready in time." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host " OK" -ForegroundColor Green
}

# ── 3. Create export directory ────────────────────────────────────────────────
if (Test-Path $ExportDir) {
    Write-Host "export/ already exists — contents will be overwritten." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path $ExportDir | Out-Null
}

# ── 4. Copy SQLite ────────────────────────────────────────────────────────────
Write-Host "Copying SQLite database..." -NoNewline
if (Test-Path $SqliteSrc) {
    Copy-Item -Path $SqliteSrc -Destination $SqliteDst -Force
    $sizeMB = [math]::Round((Get-Item $SqliteDst).Length / 1MB, 2)
    Write-Host " OK ($sizeMB MB)" -ForegroundColor Green
} else {
    Write-Host " NOT FOUND (skipped — no HK crawler data yet)" -ForegroundColor Yellow
}

# ── 5. Postgres dump ──────────────────────────────────────────────────────────
Write-Host "Dumping Postgres..." -NoNewline
docker compose exec -T postgres pg_dump -U dietsearch dietsearch | Out-File -FilePath $PgDump -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Write-Host " FAILED" -ForegroundColor Red
    exit 1
}
$pgSizeMB = [math]::Round((Get-Item $PgDump).Length / 1MB, 2)
Write-Host " OK ($pgSizeMB MB)" -ForegroundColor Green

# ── 6. Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Export complete. Files written to: $ExportDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "  food_db.sqlite   — HK crawler data"
Write-Host "  postgres_dump.sql — user accounts, saved restaurants"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. git push your branch"
Write-Host "  2. Copy the export/ folder to the new machine (USB / cloud drive)"
Write-Host "  3. On the new machine: git pull, copy export/ here, run .\setup.ps1"
Write-Host ""

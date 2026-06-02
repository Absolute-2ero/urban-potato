# setup.ps1
# Run on a new machine after cloning the repo and copying the export/ folder.
# Installs all dependencies, starts services, and imports data.
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Python 3.12 installed (py -3.12 must work)
#   - Node.js 18+ installed
#   - export/ folder placed in the project root (from export_data.ps1)
#   - backend/.env copied from the old machine (or filled in from backend/.env.example)
#
# Usage:
#   .\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root      = $PSScriptRoot
$ExportDir = Join-Path $Root "export"
$Backend   = Join-Path $Root "backend"
$Frontend  = Join-Path $Root "frontend"
$EnvFile   = Join-Path $Backend ".env"
$VenvDir   = Join-Path $Backend ".venv"

Write-Host ""
Write-Host "=== DietSearch — setup.ps1 ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Prerequisite checks ────────────────────────────────────────────────────
Write-Host "Checking prerequisites..."

# Docker
try { docker info 2>&1 | Out-Null; Write-Host "  Docker        OK" -ForegroundColor Green }
catch { Write-Host "  Docker        MISSING — install Docker Desktop" -ForegroundColor Red; exit 1 }

# Python
try { py -3.12 --version 2>&1 | Out-Null; Write-Host "  Python 3.12   OK" -ForegroundColor Green }
catch { Write-Host "  Python 3.12   MISSING — install from python.org" -ForegroundColor Red; exit 1 }

# Node
try { node --version 2>&1 | Out-Null; Write-Host "  Node.js       OK" -ForegroundColor Green }
catch { Write-Host "  Node.js       MISSING — install from nodejs.org" -ForegroundColor Red; exit 1 }

# .env
if (-not (Test-Path $EnvFile)) {
    Write-Host ""
    Write-Host "backend/.env not found!" -ForegroundColor Red
    Write-Host "Copy backend/.env from the old machine, or copy backend/.env.example and fill in your keys:" -ForegroundColor Yellow
    Write-Host "  cp backend\.env.example backend\.env" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? The app won't work without a valid .env (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") { exit 1 }
}

# export/
if (-not (Test-Path $ExportDir)) {
    Write-Host ""
    Write-Host "export/ folder not found." -ForegroundColor Yellow
    Write-Host "If you have data to import, copy the export/ folder from the old machine to the project root." -ForegroundColor Yellow
    Write-Host "Continuing without data import (fresh install)." -ForegroundColor Yellow
    Write-Host ""
}

# ── 2. Python virtualenv + dependencies ───────────────────────────────────────
Write-Host ""
Write-Host "Installing Python dependencies..." -ForegroundColor Cyan

if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtualenv..."
    py -3.12 -m venv $VenvDir
}

$pip = Join-Path $VenvDir "Scripts\pip.exe"
& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $Backend "requirements.txt") --quiet
Write-Host "  Python deps   OK" -ForegroundColor Green

# Playwright browsers
$playwright = Join-Path $VenvDir "Scripts\playwright.exe"
Write-Host "  Installing Playwright browsers (chromium)..."
& $playwright install chromium 2>&1 | Out-Null
Write-Host "  Playwright    OK" -ForegroundColor Green

# ── 3. Frontend dependencies ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
Push-Location $Frontend
npm install --silent
Pop-Location
Write-Host "  npm install   OK" -ForegroundColor Green

# ── 4. Start Docker services ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting Docker services (Postgres, Elasticsearch, Redis)..." -ForegroundColor Cyan
docker compose up -d

# Wait for Postgres
Write-Host "  Waiting for Postgres..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    docker compose exec -T postgres pg_isready -U dietsearch 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep 2
}
if (-not $ready) { Write-Host "  Postgres did not become ready in time." -ForegroundColor Red; exit 1 }
Write-Host "  Postgres      OK" -ForegroundColor Green

# Wait for Elasticsearch
Write-Host "  Waiting for Elasticsearch..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:9200/_cluster/health" -TimeoutSec 3 -ErrorAction Stop
        if ($resp.status -eq "green" -or $resp.status -eq "yellow") { $ready = $true; break }
    } catch {}
    Start-Sleep 3
}
if (-not $ready) { Write-Host "  Elasticsearch did not become ready in time." -ForegroundColor Red; exit 1 }
Write-Host "  Elasticsearch OK" -ForegroundColor Green

# ── 5. Import data (if export/ exists) ───────────────────────────────────────
if (Test-Path $ExportDir) {
    Write-Host ""
    Write-Host "Importing data from export/..." -ForegroundColor Cyan

    # Postgres restore
    $pgDump = Join-Path $ExportDir "postgres_dump.sql"
    if (Test-Path $pgDump) {
        Write-Host "  Restoring Postgres..."
        Get-Content $pgDump | docker compose exec -T postgres psql -U dietsearch dietsearch 2>&1 | Out-Null
        Write-Host "  Postgres data OK" -ForegroundColor Green
    } else {
        Write-Host "  postgres_dump.sql not found — skipping Postgres restore" -ForegroundColor Yellow
    }

    # SQLite copy
    $sqliteSrc = Join-Path $ExportDir "food_db.sqlite"
    $sqliteDst = Join-Path $Backend "data\food_db.sqlite"
    if (Test-Path $sqliteSrc) {
        New-Item -ItemType Directory -Path (Join-Path $Backend "data") -Force | Out-Null
        Copy-Item -Path $sqliteSrc -Destination $sqliteDst -Force
        Write-Host "  SQLite        OK" -ForegroundColor Green
    } else {
        Write-Host "  food_db.sqlite not found — skipping SQLite copy" -ForegroundColor Yellow
    }

    # Re-index HK restaurants from SQLite into Elasticsearch
    if (Test-Path $sqliteDst) {
        Write-Host "  Indexing HK restaurants into Elasticsearch..."
        $python = Join-Path $VenvDir "Scripts\python.exe"
        Push-Location $Backend
        & $python -m scripts.reindex_hk_from_sqlite 2>&1 | Tee-Object -Variable reindexOut | Select-String "Import complete|Error|ERROR" | ForEach-Object { Write-Host "    $_" }
        Pop-Location
        Write-Host "  HK index      OK" -ForegroundColor Green
    }

    # Import BJ data if NDJSON is present (from backend-bj repo or manual export)
    $bjNdjson = Join-Path $ExportDir "restaurants_bj.ndjson"
    if (Test-Path $bjNdjson) {
        Write-Host "  Indexing BJ restaurants into Elasticsearch..."
        $python = Join-Path $VenvDir "Scripts\python.exe"
        Push-Location $Backend
        & $python -m scripts.import_bj_data --path $bjNdjson 2>&1 | Select-String "Import complete|Error|ERROR" | ForEach-Object { Write-Host "    $_" }
        Pop-Location
        Write-Host "  BJ index      OK" -ForegroundColor Green
    } else {
        Write-Host "  restaurants_bj.ndjson not in export/ — skipping BJ import" -ForegroundColor Yellow
        Write-Host "  (to import BJ data later: py -3.12 -m scripts.import_bj_data --path <file>)" -ForegroundColor DarkGray
    }
}

# ── 6. Done ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To run the app:" -ForegroundColor Cyan
Write-Host "  Backend:   cd backend  &&  .\.venv\Scripts\uvicorn main:app --reload --port 8000"
Write-Host "  Frontend:  cd frontend &&  npm run dev"
Write-Host ""
Write-Host "Services:"
Write-Host "  Postgres        localhost:5432"
Write-Host "  Elasticsearch   localhost:9200"
Write-Host "  Redis           localhost:6379"
Write-Host ""

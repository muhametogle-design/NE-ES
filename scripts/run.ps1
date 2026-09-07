<#
=============================================================================
NE-EMIS — start the whole system locally (Windows PowerShell)

    .\scripts\run.ps1                # install deps, build frontend, seed, serve
    .\scripts\run.ps1 -Reset         # also wipe + reseed the SQLite demo database
    .\scripts\run.ps1 -NoBuild       # skip the React build (backend + API only)
    .\scripts\run.ps1 -NoReload      # no file watcher (cleanest for breakpoints)
    .\scripts\run.ps1 -Port 9000     # serve on a different port

Serves the built React SPA and the REST API from one process:
    App     http://localhost:8000
    Swagger http://localhost:8000/docs

If script execution is blocked:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
=============================================================================
#>
param(
    [switch]$Reset,
    [switch]$NoBuild,
    [switch]$NoReload,
    [int]$Port = 8000,
    [string]$Host_ = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "NE-EMIS launcher" -ForegroundColor Cyan

# --- 1/5 virtual environment -------------------------------------------------
Write-Host "1/5  Creating virtual environment (.venv)..." -ForegroundColor Green
if (-not (Test-Path ".venv")) { python -m venv .venv }
$VenvPy = ".\.venv\Scripts\python.exe"

# --- 2/5 python dependencies -------------------------------------------------
Write-Host "2/5  Installing Python dependencies..." -ForegroundColor Green
& $VenvPy -m pip install --quiet --upgrade pip
& $VenvPy -m pip install --quiet -r requirements-dev.txt

# --- 3/5 environment file ----------------------------------------------------
Write-Host "3/5  Preparing .env..." -ForegroundColor Green
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "     created .env from .env.example"
}
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }

# --- 4/5 frontend ------------------------------------------------------------
if ($NoBuild) {
    Write-Host "4/5  Skipping frontend build (-NoBuild)" -ForegroundColor Green
} else {
    Write-Host "4/5  Building React frontend (web\)..." -ForegroundColor Green
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location web
        npm install --no-audit --no-fund
        npm run build
        Pop-Location
    } else {
        Write-Warning "npm not found - skipping. The API still runs; the SPA at / will be blank."
    }
}

# --- 5/5 database ------------------------------------------------------------
Write-Host "5/5  Database..." -ForegroundColor Green
if ($Reset) {
    & $VenvPy -m scripts.seed_data --reset
} else {
    & $VenvPy -m scripts.seed_data
}

$UvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", $Host_, "--port", "$Port")
if (-not $NoReload) { $UvicornArgs += @("--reload", "--reload-dir", "app") }

Write-Host ""
Write-Host "Starting NE-EMIS on http://localhost:$Port  (docs: /docs, Ctrl+C to stop)" -ForegroundColor Yellow
Write-Host ""
& $VenvPy @UvicornArgs

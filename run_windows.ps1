param(
    [switch]$Reset,
    [switch]$NoBuild,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

# Create virtual environment if not exists
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "Installing Python dependencies..."
pip install -r requirements-dev.txt

# Check for npm and build frontend if needed
$npmAvailable = Get-Command npm -ErrorAction SilentlyContinue
if ($npmAvailable -and -not $NoBuild) {
    Write-Host "Building React frontend..."
    Set-Location web
    if (Test-Path "package-lock.json") {
        npm ci
    } else {
        npm install
    }
    npm run build
    Set-Location ..
}

# Reset database if requested
if ($Reset) {
    Write-Host "Resetting database..."
    python -m scripts.seed_data --reset
}

# Start server
Write-Host "Starting server on port $Port..."
uvicorn app.main:app --host 0.0.0.0 --port $Port --reload

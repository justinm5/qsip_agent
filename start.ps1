# QSIP Agent — one-command launch (Windows)
$ErrorActionPreference = "Stop"

Write-Host "QSIP Agent launcher" -ForegroundColor Green

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env from example. Edit it to add API keys if needed." -ForegroundColor Yellow
}

Write-Host "Building and starting services..." -ForegroundColor Cyan
docker compose up -d

Write-Host "Waiting for infrastructure..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

Write-Host "Dashboard: http://localhost:3001" -ForegroundColor Green
Write-Host "API: http://localhost:8083" -ForegroundColor Green
Write-Host "Grafana: http://localhost:3000" -ForegroundColor Green

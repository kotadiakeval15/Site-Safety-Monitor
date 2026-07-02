# Start the full stack with Docker Compose (Windows helper)
$ErrorActionPreference = "Stop"

$dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
if (Test-Path $dockerBin) {
    $env:PATH = "$dockerBin;$env:PATH"
}

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

Write-Host "Project: $projectRoot" -ForegroundColor Cyan
Write-Host "Building and starting services..." -ForegroundColor Cyan

docker compose up --build @args

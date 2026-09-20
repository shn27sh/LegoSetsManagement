# Assemble a portable Windows ZIP from PyInstaller output and frontend dist.
# Run on Windows from the repository root, for example:
#   powershell -ExecutionPolicy Bypass -File scripts/windows/assemble-portable.ps1 -Version 0.1.0

param(
    [string]$Version = "0.0.0-dev",
    [string]$PyInstallerDist = "backend\dist\lcm-server",
    [string]$FrontendDist = "frontend\dist",
    [string]$OutputDir = "dist\windows-portable"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

$stagingName = "LEGO-Collection-Manager-$Version-win64"
$staging = Join-Path $OutputDir $stagingName
$zipPath = Join-Path $OutputDir "$stagingName.zip"

if (-not (Test-Path $PyInstallerDist)) {
    throw "PyInstaller output not found: $PyInstallerDist. Run pyinstaller in backend/ first."
}
if (-not (Test-Path $FrontendDist)) {
    throw "Frontend dist not found: $FrontendDist. Run scripts/build-frontend.sh or npm run build first."
}

if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

Copy-Item -Recurse -Force $PyInstallerDist (Join-Path $staging "lcm-server")
Copy-Item -Recurse -Force $FrontendDist (Join-Path $staging "web")
New-Item -ItemType Directory -Force -Path (Join-Path $staging "data") | Out-Null

$launchSource = Join-Path $PSScriptRoot "Launch.bat"
$launchTarget = Join-Path $staging "Launch LEGO Collection Manager.bat"
Copy-Item -Force $launchSource $launchTarget

$configExample = Join-Path $PSScriptRoot "config.env.example"
Copy-Item -Force $configExample (Join-Path $staging "config.env.example")

$readmeTemplate = Join-Path $PSScriptRoot "README.txt.template"
$readme = Get-Content $readmeTemplate -Raw
$readme = $readme.Replace("@VERSION@", $Version)
Set-Content -Path (Join-Path $staging "README.txt") -Value $readme -Encoding UTF8

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Compress-Archive -Path $staging -DestinationPath $zipPath -Force

Write-Host "Portable ZIP created: $zipPath"

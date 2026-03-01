# =============================================================================
# Feetech Servo Controller - One-Command Release Builder (Windows)
# =============================================================================
# Usage: .\make_release.ps1 [version]
# Example: .\make_release.ps1 1.0.1
# =============================================================================

param(
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

$APP_NAME = "Feetech_Servo_Controller"
$DIST_NAME = "${APP_NAME}_v${Version}"

# Get script directory
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "     Feetech Servo Controller - Release Builder                   " -ForegroundColor Cyan
Write-Host "     Version: $Version                                            " -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# Clean up any previous builds
if (Test-Path "dist_temp") { Remove-Item -Recurse -Force "dist_temp" }
if (Test-Path "releases\${DIST_NAME}.zip") { Remove-Item -Force "releases\${DIST_NAME}.zip" }

# Create temp directory
New-Item -ItemType Directory -Force -Path "dist_temp\${DIST_NAME}" | Out-Null

Write-Host "[*] Packaging files..." -ForegroundColor Yellow

# Copy core files
$coreFiles = @("servo_web.py", "feetech_servo.py", "requirements.txt", "README.md")
foreach ($file in $coreFiles) {
    if (Test-Path $file) {
        Copy-Item $file "dist_temp\${DIST_NAME}\"
        Write-Host "    + $file" -ForegroundColor Gray
    }
}

# Copy LICENSE if exists
if (Test-Path "LICENSE") {
    Copy-Item "LICENSE" "dist_temp\${DIST_NAME}\"
    Write-Host "    + LICENSE" -ForegroundColor Gray
} else {
    Write-Host "    (no LICENSE file)" -ForegroundColor DarkGray
}

# Copy installers and launchers
$installers = @(
    "install_and_run.command",
    "install_and_run.bat",
    "install_windows.ps1",
    "run.command",
    "run.bat"
)
foreach ($file in $installers) {
    if (Test-Path $file) {
        Copy-Item $file "dist_temp\${DIST_NAME}\"
        Write-Host "    + $file" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "[*] Creating ZIP archive..." -ForegroundColor Yellow

# Create releases folder
New-Item -ItemType Directory -Force -Path "releases" | Out-Null

# Create ZIP
$zipPath = Join-Path $SCRIPT_DIR "releases\${DIST_NAME}.zip"
Compress-Archive -Path "dist_temp\${DIST_NAME}" -DestinationPath $zipPath -Force

# Cleanup
Remove-Item -Recurse -Force "dist_temp"

# Get file size
$fileInfo = Get-Item $zipPath
$sizeKB = [math]::Round($fileInfo.Length / 1KB, 1)
$sizeMB = [math]::Round($fileInfo.Length / 1MB, 2)
$sizeStr = if ($sizeMB -ge 1) { "${sizeMB} MB" } else { "${sizeKB} KB" }

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "  [OK] Release Created Successfully!                              " -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "   File: ${DIST_NAME}.zip ($sizeStr)" -ForegroundColor White
Write-Host "   Path: $zipPath" -ForegroundColor White
Write-Host ""
Write-Host "   Upload to Google Drive and share the link!" -ForegroundColor Cyan
Write-Host ""
Write-Host "   User Instructions:" -ForegroundColor Yellow
Write-Host "   ------------------" -ForegroundColor Yellow
Write-Host "   macOS:   Double-click 'install_and_run.command'" -ForegroundColor White
Write-Host "   Windows: Double-click 'install_and_run.bat'" -ForegroundColor White
Write-Host ""



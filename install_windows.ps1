# =============================================================================
# Feetech Servo Controller - Windows PowerShell Installer
# =============================================================================
# Right-click this file and select "Run with PowerShell"
# This creates a proper Windows shortcut with an icon
# =============================================================================

$ErrorActionPreference = "Stop"

$AppName = "Feetech Servo Controller"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopPath = [Environment]::GetFolderPath("Desktop")

Write-Host ""
Write-Host "=============================================="
Write-Host "  $AppName - Installer"
Write-Host "=============================================="
Write-Host ""

Set-Location $ScriptDir

# Check for Python
$pythonCmd = $null
try {
    $null = python --version 2>&1
    $pythonCmd = "python"
    Write-Host "√ Python found: $(python --version 2>&1)"
} catch {
    try {
        $null = python3 --version 2>&1
        $pythonCmd = "python3"
        Write-Host "√ Python found: $(python3 --version 2>&1)"
    } catch {
        Write-Host "X Python is not installed." -ForegroundColor Red
        Write-Host ""
        Write-Host "Please download and install Python from:"
        Write-Host "  https://www.python.org/downloads/"
        Write-Host ""
        Write-Host "IMPORTANT: During installation, check the box:"
        Write-Host "  'Add Python to PATH'"
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..."
& $pythonCmd -m pip install --user --upgrade pyserial flask 2>&1 | Out-Null
Write-Host "√ Dependencies installed"

# Create Windows shortcut (.lnk) using VBScript
$shortcutPath = Join-Path $DesktopPath "$AppName.lnk"
$vbsScript = @"
Set WshShell = CreateObject("WScript.Shell")
Set shortcut = WshShell.CreateShortcut("$shortcutPath")
shortcut.TargetPath = "cmd.exe"
shortcut.Arguments = "/c cd /d ""$ScriptDir"" && start """" ""http://localhost:8080"" && $pythonCmd servo_web.py"
shortcut.WorkingDirectory = "$ScriptDir"
shortcut.Description = "$AppName"
shortcut.WindowStyle = 7
shortcut.Save()
"@

$vbsFile = Join-Path $env:TEMP "create_shortcut.vbs"
$vbsScript | Out-File -FilePath $vbsFile -Encoding ASCII
cscript //nologo $vbsFile
Remove-Item $vbsFile

Write-Host "√ Desktop shortcut created"

# Create a launcher batch file as backup
$launcherPath = Join-Path $ScriptDir "run_servo_controller.bat"
@"
@echo off
title $AppName
cd /d "%~dp0"
start "" "http://localhost:8080"
$pythonCmd servo_web.py
"@ | Out-File -FilePath $launcherPath -Encoding ASCII

Write-Host ""
Write-Host "=============================================="
Write-Host "  Installation Complete!"
Write-Host "=============================================="
Write-Host ""
Write-Host "Starting $AppName..."
Write-Host "Your browser will open to: http://localhost:8080"
Write-Host ""
Write-Host "To run again later, double-click the desktop shortcut:"
Write-Host "  $shortcutPath"
Write-Host ""

# Open browser
Start-Process "http://localhost:8080"

# Run the application
& $pythonCmd servo_web.py


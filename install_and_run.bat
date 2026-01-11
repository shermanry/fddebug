@echo off
REM =============================================================================
REM Feetech Servo Controller - Windows Installer & Launcher
REM =============================================================================
REM Double-click this file to install dependencies and run the application.
REM A desktop shortcut will be created automatically.
REM =============================================================================

title Feetech Servo Controller - Installer

echo.
echo ==============================================
echo   Feetech Servo Controller - Installer
echo ==============================================
echo.

cd /d "%~dp0"

REM Check for Python 3
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo X Python is not installed.
        echo.
        echo Please download and install Python from:
        echo   https://www.python.org/downloads/
        echo.
        echo IMPORTANT: During installation, check the box:
        echo   "Add Python to PATH"
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

echo √ Python found

REM Install dependencies
echo.
echo Installing dependencies...
%PYTHON_CMD% -m pip install --user --upgrade pyserial flask >nul 2>&1
if errorlevel 1 (
    %PYTHON_CMD% -m pip install pyserial flask
)
echo √ Dependencies installed

REM Create desktop shortcut
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_NAME=Feetech Servo Controller.bat
set SHORTCUT_PATH=%DESKTOP%\%SHORTCUT_NAME%

echo @echo off > "%SHORTCUT_PATH%"
echo title Feetech Servo Controller >> "%SHORTCUT_PATH%"
echo cd /d "%~dp0" >> "%SHORTCUT_PATH%"
echo start "" "http://localhost:8080" >> "%SHORTCUT_PATH%"
echo %PYTHON_CMD% servo_web.py >> "%SHORTCUT_PATH%"

echo √ Desktop shortcut created

echo.
echo ==============================================
echo   Installation Complete!
echo ==============================================
echo.
echo Starting Feetech Servo Controller...
echo Your browser will open to: http://localhost:8080
echo.
echo To run again later, double-click:
echo   "%SHORTCUT_PATH%"
echo.

REM Open browser
start "" "http://localhost:8080"

REM Run the application
%PYTHON_CMD% servo_web.py

pause


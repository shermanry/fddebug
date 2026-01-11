@echo off
REM Feetech Servo Controller - Quick Launch (Windows)
title Feetech Servo Controller
cd /d "%~dp0"
echo Starting Feetech Servo Controller...
echo Open your browser to: http://localhost:8080
start "" "http://localhost:8080"
python servo_web.py
pause


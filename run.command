#!/bin/bash
# =============================================================================
# Feetech Servo Controller - Quick Launch (macOS)
# =============================================================================
cd "$(dirname "$0")"
echo "Starting Feetech Servo Controller..."
echo "Open your browser to: http://localhost:8080"
(sleep 2 && open "http://localhost:8080") &
python3 servo_web.py


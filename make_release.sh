#!/bin/bash
# =============================================================================
# Feetech Servo Controller - One-Command Release Builder
# =============================================================================
# Usage: ./make_release.sh [version]
# Example: ./make_release.sh 1.0.1
# =============================================================================

set -e

# Get version from argument or default
VERSION="${1:-1.0.0}"
APP_NAME="Feetech_Servo_Controller"
DIST_NAME="${APP_NAME}_v${VERSION}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Feetech Servo Controller - Release Builder               ║"
echo "║     Version: $VERSION                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Clean up any previous builds
rm -rf dist_temp "${DIST_NAME}.zip" 2>/dev/null || true

# Create temp directory
mkdir -p "dist_temp/${DIST_NAME}"

echo "📦 Packaging files..."

# Copy core files
cp servo_web.py "dist_temp/${DIST_NAME}/"
cp feetech_servo.py "dist_temp/${DIST_NAME}/"
cp requirements.txt "dist_temp/${DIST_NAME}/"
cp README.md "dist_temp/${DIST_NAME}/"
cp LICENSE "dist_temp/${DIST_NAME}/" 2>/dev/null || echo "   (no LICENSE file)"

# Copy installers and launchers
cp install_and_run.command "dist_temp/${DIST_NAME}/"
cp install_and_run.bat "dist_temp/${DIST_NAME}/"
cp install_windows.ps1 "dist_temp/${DIST_NAME}/"
cp run.command "dist_temp/${DIST_NAME}/"
cp run.bat "dist_temp/${DIST_NAME}/"

# Make macOS scripts executable
chmod +x "dist_temp/${DIST_NAME}/install_and_run.command"
chmod +x "dist_temp/${DIST_NAME}/run.command"

echo "📦 Creating ZIP archive..."

# Create releases folder
mkdir -p releases

# Create ZIP
cd dist_temp
zip -rq "../releases/${DIST_NAME}.zip" "${DIST_NAME}"
cd ..

# Cleanup
rm -rf dist_temp

# Get file size
SIZE=$(ls -lh "releases/${DIST_NAME}.zip" | awk '{print $5}')

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Release Created Successfully!                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "   📁 File: ${DIST_NAME}.zip ($SIZE)"
echo "   📍 Path: ${SCRIPT_DIR}/releases/${DIST_NAME}.zip"
echo ""
echo "   📤 Upload to Google Drive and share the link!"
echo ""
echo "   📋 User Instructions:"
echo "   ─────────────────────"
echo "   macOS:   Double-click 'install_and_run.command'"
echo "   Windows: Double-click 'install_and_run.bat'"
echo ""


#!/bin/bash
# =============================================================================
# Feetech Servo Controller - macOS Installer & Launcher
# =============================================================================
# Double-click this file to install dependencies and run the application.
# A desktop shortcut will be created automatically.
# =============================================================================

set -e

APP_NAME="Feetech Servo Controller"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DESKTOP_DIR="$HOME/Desktop"

echo ""
echo "=============================================="
echo "  $APP_NAME - Installer"
echo "=============================================="
echo ""

cd "$SCRIPT_DIR"

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed."
    echo ""
    echo "Please install Python 3 from: https://www.python.org/downloads/"
    echo "Or install via Homebrew: brew install python3"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check/install pip
if ! python3 -m pip --version &> /dev/null; then
    echo "Installing pip..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py --user
    rm get-pip.py
fi

echo "✓ pip found"

# Install dependencies
echo ""
echo "Installing dependencies..."
python3 -m pip install --user --upgrade pyserial flask 2>/dev/null || \
python3 -m pip install --user pyserial flask

echo "✓ Dependencies installed"

# Create desktop shortcut (macOS .command file)
SHORTCUT="$DESKTOP_DIR/Feetech Servo Controller.command"
cat > "$SHORTCUT" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")"
LAUNCHER

echo "cd \"$SCRIPT_DIR\" && python3 servo_web.py" >> "$SHORTCUT"
chmod +x "$SHORTCUT"

echo ""
echo "✓ Desktop shortcut created"
echo ""
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
echo "Starting Feetech Servo Controller..."
echo "Your browser will open to: http://localhost:8080"
echo ""
echo "To run again later, double-click:"
echo "  '$SHORTCUT'"
echo ""

# Open browser after a delay
(sleep 2 && open "http://localhost:8080") &

# Run the application
python3 servo_web.py


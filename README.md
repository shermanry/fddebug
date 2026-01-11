# Feetech Servo Controller

A cross-platform GUI application for controlling Feetech servos (SCS, SMS, STS series).

![Screenshot](https://via.placeholder.com/800x500?text=Feetech+Servo+Controller)

## Features

- **Multi-servo control**: Control up to 16 servos simultaneously in a 4x4 grid
- **Auto-detection**: Automatically detects SCS vs STS/SMS servo types
- **Real-time monitoring**: Live position, voltage, temperature, and load readings
- **Full EPROM access**: PID tuning, punch, protection limits, LED alarms, and more
- **Torque control**: Quick enable/disable torque from the main UI
- **Cross-platform**: Works on macOS and Windows

## Supported Hardware

### USB Adapters

| Adapter | Chip | Status |
|---------|------|--------|
| **Feetech URT-1** | CH340 | ✅ Fully supported |
| **Waveshare Bus Servo Adapter v1.1** | CH340/CP210x | ✅ Fully supported |
| Generic USB-TTL | CH340/CH341/CP210x/FTDI | ✅ Should work |

### Servos

| Type | Examples | Resolution | Features |
|------|----------|------------|----------|
| **SCS** | SCS0009, SCS15, SCS215 | 10-bit (0-1023) | Position control |
| **STS/SMS** | STS3215, SMS_STS | 12-bit (0-4095) | Multi-turn, mode selection, offset |

---

## Installation

### Option 1: Easy Install (Recommended)

#### macOS

1. Download and extract the ZIP file
2. Double-click **`install_and_run.command`**
3. If prompted, allow the file to run in System Preferences → Security & Privacy
4. A desktop shortcut will be created automatically

#### Windows

1. Download and extract the ZIP file
2. Double-click **`install_and_run.bat`**
3. A desktop shortcut will be created automatically

> **Note**: Python 3 is required. Download from [python.org](https://www.python.org/downloads/) if not installed.
> On Windows, make sure to check **"Add Python to PATH"** during installation.

### Running Again After Installation

After the first install, you can run the app using:

| Method | macOS | Windows |
|--------|-------|---------|
| **Desktop Shortcut** | Double-click shortcut on Desktop | Double-click shortcut on Desktop |
| **Quick Launch** | Double-click `run.command` | Double-click `run.bat` |
| **Command Line** | `python3 servo_web.py` | `python servo_web.py` |

Then open your browser to: **http://localhost:8080**

### Option 2: Manual Installation

```bash
# Clone or download the repository
cd fddebug

# Install dependencies
pip install -r requirements.txt

# Run the application
python servo_web.py
```

Then open your browser to: **http://localhost:8080**

### Creating a Release for Distribution

To create a distributable ZIP file (for uploading to Google Drive, etc.):

```bash
./make_release.sh 1.0.0
```

This creates `Feetech_Servo_Controller_v1.0.0.zip` containing everything users need.

---

## Usage

### Connecting

1. Plug in your URT-1 USB debugger
2. Select the serial port from the dropdown (usually `/dev/cu.usbserial-*` on Mac, `COM*` on Windows)
3. Click **Connect**

### Controlling Servos

1. Enter the servo ID in any card (1-253)
2. Click **Connect** on that card
3. Use the slider to move the servo
4. Use **MIN/MID/MAX** buttons for quick positioning
5. Toggle **Torque ON/OFF** to enable/disable holding

### Programming Servos

1. Connect to a servo
2. Click **⚙️ Program** to open the settings modal
3. Unlock EPROM before making changes
4. Modify settings (ID, mode, limits, etc.)
5. Lock EPROM to save changes permanently

---

## Python Library

You can also use the library directly in your own projects:

```python
from feetech_servo import FeetechServo, SCSController, STSController

# For SCS servos (SCS0009, etc.)
servo = SCSController()
servo.open('/dev/cu.usbserial-1130')

# Or for STS servos (STS3215, etc.)
servo = STSController()
servo.open('/dev/cu.usbserial-1130')

# Auto-detect type
servo = FeetechServo()
servo.open('/dev/cu.usbserial-1130')
servo_type = servo.detect_type(1)  # Returns 'scs' or 'sts'
servo.configure_for_type(servo_type)

# Control servo
servo.write_position(1, 512, speed=1000)
position = servo.read_position(1)
print(f"Position: {position}")

# Read status
status = servo.get_status(1)
print(f"Voltage: {status.voltage}V, Temp: {status.temperature}°C")

servo.close()
```

---

## Troubleshooting

### Serial Port Not Found

- **macOS**: Install CH340 driver from the included `CH340_URT.rar`
- **Windows**: Driver usually installs automatically; if not, extract and install from `CH340_URT.rar`

### Permission Denied (macOS)

```bash
sudo chmod 666 /dev/cu.usbserial-*
```

### Servo Not Responding

1. Check wiring (VCC, GND, DATA)
2. Verify servo ID (default is usually 1)
3. Try scanning: the app will find all connected servos
4. Check baud rate (default 1,000,000)

### ID Change Not Persisting

Make sure to:
1. Click "Unlock EPROM" before changing
2. Click "Lock EPROM" after changing (this saves to flash)

---

## Original FD Debugger Versions

| Version | Servo Support | Description | Status |
|---------|---------------|-------------|--------|
| FD1.9.6 | SCS/SMS | | Discontinued |
| FD1.9.7 | SCS/SMS | | Discontinued |
| FD1.9.8 | SCS/SMS/STS | Online firmware upgrade | Discontinued |
| FD1.9.8.1 | FT Full Series | Online servo config loading | Stable |
| FD1.9.8.2 | FT Full Series | Offline config import | Stable |
| FD1.9.8.3 | FT Full Series | Bug fixes | Stable |
| FD1.9.8.4 | FT Full Series | HTS/HLS support | Stable |
| FD1.9.8.5 | FT Full Series | Chinese/English switching | Stable |
| RC_Servo_Assist_2.3 | FT RC PWM Servo | | Stable |
| RC_Servo_Assist_2.4 | FT RC PWM Servo | English interface fix | Beta |
| FUServo_Debuger_2.0 | FT FU Bus Servo | TTL port debugging only | Discontinued |
| FTCanDebug-251121 | FT CAN Bus Servo | CAN bus debugging | Beta |

---

## License

MIT License - See LICENSE file for details.
to create release ./make_release.sh 1.1.0
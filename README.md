# Feetech Servo Controller

A cross-platform GUI application and Python library for controlling Feetech servos (SCS, SMS, STS, and HLS series).

![Screenshot](https://via.placeholder.com/800x500?text=Feetech+Servo+Controller)

## Features

- **Multi-servo control**: Control up to 16 servos simultaneously in a 4x4 grid
- **Auto-detection**: Automatically detects SCS vs STS/SMS vs HLS servo types
- **Real-time monitoring**: Live position, voltage, temperature, load, and current readings
- **Full EPROM / SRAM access**: PID tuning, punch, protection limits, LED alarms, runtime PID, and torque limits
- **Torque control**: Quick enable/disable torque from the main UI, plus HLS torque-limiting support
- **Cross-platform**: Works on macOS, Linux, and Windows

## Supported Hardware

### Port Interfaces & Adapters

| Interface | Hardware / Adapter | Device / Port Path | Status |
|-----------|-------------------|-------------------|--------|
| **USB Serial** | Feetech URT-1 (CH340/CH343) | `/dev/ttyUSB*`, `/dev/cu.usbserial-*`, `COM*` | ✅ Fully supported |
| **USB Serial** | Waveshare Bus Servo Adapter v1.1 | `/dev/ttyUSB*`, `COM*` | ✅ Fully supported |
| **Hardware UART** | **Raspberry Pi 4 + URT-1** (GPIO) | `/dev/serial0`, `/dev/ttyAMA0`, `/dev/ttyAMA1..4` | ✅ Fully supported |
| **Hardware UART** | Generic Linux SBC + URT-1 (Jetson, etc.) | `/dev/ttyTHS*`, `/dev/ttyS*` | ✅ Supported |
| Generic USB-TTL | CH340 / CP210x / FTDI | Any standard COM / tty port | ✅ Supported |

### Servos

| Type | Examples | Resolution | Features |
|------|----------|------------|----------|
| **SCS** | SCS0009, SCS15, SCS215 | 10-bit (0-1023) | Position control |
| **STS/SMS** | STS3215, SMS_STS | 12-bit (0-4095) | Multi-turn, mode selection, offset |
| **HLS** | HLS3606 | 12-bit (0-4095) | Torque control (FOC), current/velocity PID, runtime SRAM PID, signed current |

---

## Installation & Running

### Using `uv` (Fastest & Recommended)

With [`uv`](https://github.com/astral-sh/uv) installed:

```bash
# Run directly (automatically manages virtualenv and dependencies):
uv run feetech-web

# Or specify a custom port / host:
uv run feetech-web --port 8081

# Install as a global CLI tool:
uv tool install .

# Or install editable into an existing environment:
uv pip install -e .
```

### Option 1: Easy Install Scripts

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

| Method | Command / Action |
|--------|------------------|
| **uv** | `uv run feetech-web` |
| **Desktop Shortcut** | Double-click shortcut on Desktop |
| **Quick Launch** | Double-click `run.command` (macOS) or `run.bat` (Windows) |
| **Command Line** | `python3 servo_web.py` (or `python servo_web.py --port 8080`) |

Then open your browser to: **http://localhost:8080**

### Option 2: Standard pip Installation

```bash
# Clone or download the repository
cd fddebug

# Install dependencies
pip install -r requirements.txt
# Or install package in editable mode:
pip install -e .

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

### Connecting via USB

1. Plug in your URT-1 USB debugger or Waveshare adapter
2. Select the serial port from the dropdown (e.g. `/dev/cu.usbserial-*` on macOS, `/dev/ttyUSB*` on Linux, `COM*` on Windows)
3. Select your baud rate (default: `1,000,000`)
4. Click **Connect**

### Connecting via Raspberry Pi 4 Hardware UART + URT-1

Connecting the URT-1 directly to the Raspberry Pi 4's hardware UART provides lower latency and avoids USB cabling overhead in embedded robot arms and cobots.

#### 1. Hardware Wiring

Connect the Pi 4's 40-pin GPIO header to the URT-1's UART/TTL pin header:

| Raspberry Pi 4 Pin | Pi Function | URT-1 Pin | Notes |
|--------------------|-------------|-----------|-------|
| **Pin 8** | GPIO 14 (TXD0) | **RXD** | Data transmit from Pi to URT-1 |
| **Pin 10** | GPIO 15 (RXD0) | **TXD** | Data receive from URT-1 to Pi |
| **Pin 6 / 9 / 14** | GND | **GND** | Common ground (mandatory) |
| External Power Supply | +V / GND | **VIN / GND** | 6V–12V DC power for servos. **Do not power servos from Pi 5V pin!** |

> **Direction Control**: The URT-1 has built-in automatic half-duplex direction control for the Feetech 1-wire bus. No extra GPIO direction pins or manual RTS toggling are needed.

#### 2. Raspberry Pi OS Configuration

1. Disable the serial console and enable hardware UART:
   ```bash
   sudo raspi-config
   ```
   Navigate to: **Interface Options** -> **Serial Port**:
   - *"Would you like a login shell to be accessible over serial?"* -> **No**
   - *"Would you like the serial port hardware to be enabled?"* -> **Yes**

2. Add your user to the `dialout` group for permissions:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   *(Log out and back in for this to take effect)*

3. *(Recommended)* Ensure high-speed PL011 UART is assigned to GPIO 14/15 by adding this to `/boot/firmware/config.txt` (or `/boot/config.txt` on older OS releases):
   ```ini
   enable_uart=1
   dtoverlay=disable-bt
   ```
   *(Reboot after modifying `config.txt`)*

   *Optional: If using Pi 4 additional PL011 UARTs (UART2 through UART5):*
   - `dtoverlay=uart2` -> GPIO 0 (TX) / GPIO 1 (RX) -> `/dev/ttyAMA1`
   - `dtoverlay=uart3` -> GPIO 4 (TX) / GPIO 5 (RX) -> `/dev/ttyAMA2`
   - `dtoverlay=uart4` -> GPIO 8 (TX) / GPIO 9 (RX) -> `/dev/ttyAMA3`
   - `dtoverlay=uart5` -> GPIO 12 (TX) / GPIO 13 (RX) -> `/dev/ttyAMA4`

#### 3. Connecting

- **From Web UI**: Select `/dev/serial0` (or `/dev/ttyAMA0`) from the dropdown (or choose *Custom port path...*), ensure baud rate is `1,000,000`, and click **Connect**.
- **Headless / Auto-Connect at boot**:
  ```bash
  uv run feetech-web --serial-port /dev/serial0 --baudrate 1000000 --host 0.0.0.0 --port 8080
  ```
- **In Python code**:
  ```python
  from feetech_servo import FeetechServo

  servo = FeetechServo()
  if servo.open('/dev/serial0', baudrate=1000000):
      print("Connected to URT-1 over Pi 4 hardware UART!")
  ```

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
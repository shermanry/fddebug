"""
Basic Position Control Example

Demonstrates simple position control for a single servo.
"""

from machine import UART, Pin
from feetech import ServoBus, Servo
import time

# ============================================================
# HARDWARE SETUP - Adjust for your board
# ============================================================

# For WIZnet RP2040 with Waveshare adapter
# Connect adapter TX -> Pico RX (GP1)
# Connect adapter RX -> Pico TX (GP0)
uart = UART(0, baudrate=1000000, tx=Pin(0), rx=Pin(1))

# ============================================================
# INITIALIZATION
# ============================================================

print("Initializing servo bus...")
bus = ServoBus(uart)

# Scan for connected servos
print("Scanning for servos...")
found = bus.scan(start_id=1, end_id=10)
print(f"Found servos: {found}")

if not found:
    print("No servos found! Check connections.")
    raise SystemExit

# Create servo controller for first found servo
servo_id = found[0]
servo = Servo(bus, servo_id)
print(f"Using servo ID {servo_id}, type: {servo.servo_type.name}")

# ============================================================
# BASIC POSITION CONTROL
# ============================================================

# Read current position
pos = servo.read_position()
print(f"Current position: {pos} ({servo.angle:.1f}°)")

# Enable torque
servo.enable()
print("Torque enabled")

# Move to center position (different for SCS vs STS)
if servo.servo_type.name == "SCS":
    center = 512  # 1024 resolution
    max_pos = 1023
else:
    center = 2048  # 4096 resolution
    max_pos = 4095

print(f"Moving to center ({center})...")
servo.move_to(center)
bus.execute()  # Send the command
time.sleep(1)

# Read new position
pos = servo.read_position()
print(f"Position after move: {pos} ({servo.angle:.1f}°)")

# Move using speed control
print("Moving with speed control...")
servo.move_to(0, speed=200)  # Move to 0 at speed 200
bus.execute()
time.sleep(2)

servo.move_to(max_pos, speed=200)  # Move to max at speed 200
bus.execute()
time.sleep(2)

# Return to center
servo.move_to(center)
bus.execute()
time.sleep(1)

# ============================================================
# MOVE BY ANGLE
# ============================================================

print("\nMoving by angle...")
servo.move_to_angle(0)
bus.execute()
time.sleep(1)

servo.move_to_angle(90)
bus.execute()
time.sleep(1)

servo.move_to_angle(180)
bus.execute()
time.sleep(1)

servo.move_to_angle(90)
bus.execute()
time.sleep(1)

# ============================================================
# RELATIVE MOVES
# ============================================================

print("\nRelative moves...")
for i in range(4):
    servo.move_by(100)  # Move 100 ticks forward
    bus.execute()
    time.sleep(0.5)

for i in range(4):
    servo.move_by(-100)  # Move 100 ticks back
    bus.execute()
    time.sleep(0.5)

# ============================================================
# READ STATUS
# ============================================================

print("\nFinal status:")
status = servo.read_status()
print(f"  Position: {status['position']} ({status['angle']:.1f}°)")
print(f"  Speed: {status['speed']}")
print(f"  Load: {status['load']}")
print(f"  Voltage: {status['voltage']:.1f}V")
print(f"  Temperature: {status['temperature']}°C")

# Disable torque
servo.disable()
print("\nTorque disabled. Done!")


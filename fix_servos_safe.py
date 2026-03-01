#!/usr/bin/env python3
"""
Fix servos 9 and 10 by setting known-good EPROM values.
Does NOT copy voltage limits (they're weird on servo 8).
Stop the GUI first, then run: python3 fix_servos_safe.py
"""
from feetech_servo import FeetechServo, SCSReg
import serial.tools.list_ports
import time

ports = [p.device for p in serial.tools.list_ports.comports() if 'usbserial' in p.device or 'usbmodem' in p.device]
if not ports:
    print("No servo adapter found!")
    exit(1)

print(f'Using port: {ports[0]}')

servo = FeetechServo()
if not servo.open(ports[0]):
    print("Failed to open port - is the GUI still running?")
    exit(1)

servo.configure_for_type('sts')

# Factory-like defaults for STS3215
# These are safe, known-good values
STS_DEFAULTS = {
    # Voltage limits - proper values for 12V servo
    17: 140,    # Max Voltage = 14.0V  
    18: 40,     # Min Voltage = 4.0V
    
    # Angle limits - full range
    9: 0,       # Min Angle low byte
    10: 0,      # Min Angle high byte  (0)
    11: 0xFF,   # Max Angle low byte
    12: 0x0F,   # Max Angle high byte  (4095)
    
    # Temperature
    14: 85,     # Max Temp = 85°C (reasonable, not 140°C)
    
    # Torque settings
    16: 0xE8,   # Max Torque low byte
    # Note: addr 17 is SHARED with Max Voltage! Don't overwrite here.
    19: 80,     # Overload protection = 80%
    
    # Alarm settings
    25: 0x24,   # LED Alarm: Overheat + Overload only (not voltage)
    26: 0x24,   # Unload on: Overheat + Overload only
    
    # Offset
    31: 0,      # Offset low byte
    32: 0,      # Offset high byte (0)
    
    # Mode
    33: 0,      # Position mode
    
    # Acceleration
    41: 50,     # Default acceleration
}

print("\n=== Current state ===")
for sid in [8, 9, 10]:
    v = servo.read_voltage(sid)
    e = servo.read_byte(sid, 65)
    pos = servo.read_position(sid)
    print(f"Servo {sid}: Voltage={v}V, Error={e}, Position={pos}")

print("\n=== Fixing servos 9 and 10 with safe defaults ===")

for sid in [9, 10]:
    print(f"\nServo {sid}:")
    
    servo.unlock_eprom(sid, 'sts')
    time.sleep(0.05)
    
    for addr, value in STS_DEFAULTS.items():
        servo.write_byte(sid, addr, value)
        time.sleep(0.005)
    
    # Also need to set Max Torque high byte carefully
    # Addr 17 is shared, but we need torque = 1000 = 0x03E8
    # So high byte should be 0x03, but that conflicts with voltage 14.0V (0x8C)
    # The solution: Set addr 17 to 0x8C (14.0V) and accept lower max torque
    # Or set a compromise value
    # Actually, let's explicitly set max torque = 1000
    servo.write_word(sid, 16, 1000)  # This writes both addr 16 and 17
    time.sleep(0.005)
    # Then re-set voltage limit
    servo.write_byte(sid, 17, 140)  # Max voltage 14.0V
    time.sleep(0.005)
    
    servo.lock_eprom(sid, 'sts')
    time.sleep(0.1)
    
    # Verify key settings
    max_v = servo.read_byte(sid, 17)
    min_v = servo.read_byte(sid, 18)
    max_torque = servo.read_word(sid, 16)
    print(f"  Voltage limits: {min_v/10.0}V - {max_v/10.0}V")
    print(f"  Max torque: {max_torque}")
    
print("\n=== Final check (before power cycle) ===")
for sid in [8, 9, 10]:
    v = servo.read_voltage(sid)
    e = servo.read_byte(sid, 65)
    print(f"Servo {sid}: Voltage={v}V, Error={e}")

servo.close()

print("\n" + "="*50)
print("IMPORTANT: Power cycle servos 9 and 10 NOW!")
print("The voltage error should clear after power cycle.")
print("="*50)



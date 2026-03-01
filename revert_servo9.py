#!/usr/bin/env python3
"""
Revert EPROM changes made to servo 9.
Stop the GUI first, then run: python3 revert_servo9.py
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

print("\n=== Current state of servo 9 ===")
v = servo.read_voltage(9)
print(f"Voltage: {v}V")
e = servo.read_byte(9, 65)
print(f"Error status: {e}")

max_v = servo.read_byte(9, 17)
min_v = servo.read_byte(9, 18)
print(f"Voltage limits: Min={min_v/10.0}V, Max={max_v/10.0}V")

offset_raw = servo.read_word(9, 31)
if offset_raw & 0x8000:
    offset = -(offset_raw & 0x7FFF)
else:
    offset = offset_raw
print(f"Offset: {offset}")

min_lim = servo.read_word(9, 9)
max_lim = servo.read_word(9, 11)
print(f"Angle limits: {min_lim} - {max_lim}")

print("\n=== Restoring safe defaults ===")

servo.unlock_eprom(9, 'sts')

# Restore voltage limits for STS3215 (4-14V range)
servo.write_byte(9, 17, 140)  # Max voltage 14.0V
servo.write_byte(9, 18, 40)   # Min voltage 4.0V
print("Restored voltage limits: 4.0V - 14.0V")

# Restore offset to 0
servo.write_word(9, 31, 0)
print("Restored offset: 0")

# Restore angle limits to full range
servo.write_word(9, 9, 0)     # Min = 0
servo.write_word(9, 11, 4095) # Max = 4095
print("Restored angle limits: 0 - 4095")

# Restore LED alarm mask to default (all alarms)
servo.write_byte(9, 25, 0x7F)
print("Restored LED alarm mask: 0x7F (all alarms)")

servo.lock_eprom(9, 'sts')
time.sleep(0.2)

print("\n=== Verification ===")
v = servo.read_voltage(9)
print(f"Voltage: {v}V")
e = servo.read_byte(9, 65)
print(f"Error status: {e} (0 = OK)")

max_v = servo.read_byte(9, 17)
min_v = servo.read_byte(9, 18)
print(f"Voltage limits: Min={min_v/10.0}V, Max={max_v/10.0}V")

servo.close()
print("\nDone! Power cycle servo 9 to clear any latched errors.")


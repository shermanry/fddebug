#!/usr/bin/env python3
from feetech_servo import FeetechServo, SCSReg
import serial.tools.list_ports

ports = [p.device for p in serial.tools.list_ports.comports() if 'usbserial' in p.device or 'usbmodem' in p.device]
print('Port:', ports[0])

servo = FeetechServo()
servo.open(ports[0])
servo.configure_for_type('sts')

# Use exact same method as GUI
v9 = servo.read_voltage(9)
v10 = servo.read_voltage(10)
print('Servo 9 voltage:', v9, 'V')
print('Servo 10 voltage:', v10, 'V')

# Check error status
e9 = servo.read_byte(9, 65)
e10 = servo.read_byte(10, 65)
print('Servo 9 error:', e9)
print('Servo 10 error:', e10)

# Check what I might have broken
print()
print('Checking voltage limits:')
for sid in [9, 10]:
    max_v = servo.read_byte(sid, 17)
    min_v = servo.read_byte(sid, 18)
    print(f'  Servo {sid}: Max={max_v/10.0}V, Min={min_v/10.0}V')

servo.close()



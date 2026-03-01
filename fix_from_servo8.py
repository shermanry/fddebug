#!/usr/bin/env python3
"""
Read EPROM from working servo 8, save to file, and copy to broken servos 9 and 10.
Stop the GUI first, then run: python3 fix_from_servo8.py
"""
from feetech_servo import FeetechServo, SCSReg
import serial.tools.list_ports
import time
import json

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

# Read full EPROM from servo 8 (first 64 bytes contain all settings)
print("\n=== Reading EPROM from servo 8 (working) ===")
eprom_8 = servo.read_bytes(8, 0, 64)

if not eprom_8 or len(eprom_8) < 64:
    print("Failed to read EPROM from servo 8!")
    servo.close()
    exit(1)

print(f"Read {len(eprom_8)} bytes from servo 8")

# Save to file
eprom_hex = [f"0x{b:02X}" for b in eprom_8]
with open("servo8_eprom.json", "w") as f:
    json.dump({
        "servo_id": 8,
        "eprom_bytes": list(eprom_8),
        "eprom_hex": eprom_hex
    }, f, indent=2)
print("Saved to servo8_eprom.json")

# Print key registers from servo 8
print("\n=== Servo 8 Key Settings ===")
print(f"  ID (addr 5):           {eprom_8[5]}")
print(f"  Baud Rate (addr 6):    {eprom_8[6]}")
print(f"  Min Angle (addr 9-10): {eprom_8[9] | (eprom_8[10] << 8)}")
print(f"  Max Angle (addr 11-12): {eprom_8[11] | (eprom_8[12] << 8)}")
print(f"  Max Temp (addr 14):    {eprom_8[14]}°C")
print(f"  Max Torque (addr 16-17): {eprom_8[16] | (eprom_8[17] << 8)}")
print(f"  Min Voltage (addr 18): {eprom_8[18]/10.0}V")
print(f"  Max Voltage (addr 17): {eprom_8[17]/10.0}V")  # Note: addr 17 is shared
print(f"  Overload Torque (addr 19): {eprom_8[19]}%")
print(f"  LED Alarm (addr 25):   0x{eprom_8[25]:02X}")
print(f"  Unload Cond (addr 26): 0x{eprom_8[26]:02X}")
offset_raw = eprom_8[31] | (eprom_8[32] << 8)
if offset_raw & 0x8000:
    offset = -(offset_raw & 0x7FFF)
else:
    offset = offset_raw
print(f"  Offset (addr 31-32):   {offset}")
print(f"  Mode (addr 33):        {eprom_8[33]}")

# Read EPROMs from servos 9 and 10 for comparison
print("\n=== Comparing with servos 9 and 10 ===")
for sid in [9, 10]:
    eprom = servo.read_bytes(sid, 0, 64)
    if not eprom or len(eprom) < 64:
        print(f"\nServo {sid}: FAILED TO READ")
        continue
    
    print(f"\nServo {sid} differences from servo 8:")
    diff_count = 0
    for addr in range(64):
        if eprom[addr] != eprom_8[addr]:
            diff_count += 1
            print(f"  Addr {addr:2d}: servo8=0x{eprom_8[addr]:02X} ({eprom_8[addr]:3d})  servo{sid}=0x{eprom[addr]:02X} ({eprom[addr]:3d})")
    
    if diff_count == 0:
        print("  (no differences)")
    else:
        print(f"  Total: {diff_count} differences")

# Now copy from servo 8 to servos 9 and 10
print("\n=== Copying settings from servo 8 to servos 9 and 10 ===")

# Registers to copy (skip ID at addr 5, and skip baud at addr 6)
# We'll copy everything EXCEPT the ID
registers_to_copy = list(range(0, 5)) + list(range(6, 64))  # Skip addr 5 (ID)

for target_id in [9, 10]:
    print(f"\nCopying to servo {target_id}...")
    
    servo.unlock_eprom(target_id, 'sts')
    time.sleep(0.05)
    
    # Copy byte by byte (skip ID)
    for addr in registers_to_copy:
        servo.write_byte(target_id, addr, eprom_8[addr])
        time.sleep(0.002)  # Small delay between writes
    
    servo.lock_eprom(target_id, 'sts')
    time.sleep(0.1)
    
    # Verify
    verify = servo.read_bytes(target_id, 0, 64)
    if verify:
        mismatch = 0
        for addr in registers_to_copy:
            if verify[addr] != eprom_8[addr]:
                mismatch += 1
                print(f"  MISMATCH at addr {addr}: wrote 0x{eprom_8[addr]:02X}, read 0x{verify[addr]:02X}")
        if mismatch == 0:
            print(f"  Verified OK - all {len(registers_to_copy)} registers match")
    else:
        print(f"  Failed to verify servo {target_id}")

# Final check
print("\n=== Final Verification ===")
for sid in [8, 9, 10]:
    v = servo.read_voltage(sid)
    e = servo.read_byte(sid, 65)
    print(f"Servo {sid}: Voltage={v}V, Error={e}")

servo.close()
print("\nDone! Power cycle servos 9 and 10 to apply changes.")



"""
PID Tuning Example

Demonstrates how to adjust PID parameters for different
motion characteristics.

Higher P = Faster response, may overshoot
Higher I = Reduces steady-state error, may cause oscillation
Higher D = Reduces overshoot, may cause jitter

For position servos:
- Start with low I (0-10)
- Adjust P for response speed
- Add D to reduce overshoot
"""

from machine import UART, Pin
from feetech import ServoBus, Servo
import time

# ============================================================
# SETUP
# ============================================================

uart = UART(0, baudrate=1000000, tx=Pin(0), rx=Pin(1))
bus = ServoBus(uart)

found = bus.scan()
if not found:
    print("No servos found!")
    raise SystemExit

servo = Servo(bus, found[0])
print(f"Servo {servo.id}, type: {servo.servo_type.name}")

# ============================================================
# READ CURRENT PID VALUES
# ============================================================

protocol = bus.protocol
stype = servo.servo_type

p = protocol.read(servo.id, stype.reg_p, 1)[0]
i = protocol.read(servo.id, stype.reg_i, 1)[0]
d = protocol.read(servo.id, stype.reg_d, 1)[0]

print(f"\nCurrent PID: P={p}, I={i}, D={d}")

# ============================================================
# TEST DIFFERENT PID SETTINGS
# ============================================================

def test_response(name: str, test_moves: int = 3):
    """Test servo response with current PID settings."""
    print(f"\nTesting: {name}")
    servo.enable()
    
    center = stype.resolution // 2
    offset = 300
    
    for i in range(test_moves):
        # Quick back-and-forth to see response
        servo.move_to(center + offset)
        bus.execute()
        time.sleep(0.5)
        
        servo.move_to(center - offset)
        bus.execute()
        time.sleep(0.5)
    
    servo.move_to(center)
    bus.execute()
    time.sleep(0.3)

# ============================================================
# CONSERVATIVE SETTINGS
# ============================================================

print("\n=== Conservative PID (slow, no overshoot) ===")
servo.set_pid(p=16, i=0, d=8)
test_response("Conservative P=16, I=0, D=8")

# ============================================================
# BALANCED SETTINGS
# ============================================================

print("\n=== Balanced PID (moderate response) ===")
servo.set_pid(p=32, i=0, d=32)
test_response("Balanced P=32, I=0, D=32")

# ============================================================
# AGGRESSIVE SETTINGS
# ============================================================

print("\n=== Aggressive PID (fast, may overshoot) ===")
servo.set_pid(p=64, i=0, d=16)
test_response("Aggressive P=64, I=0, D=16")

# ============================================================
# WITH INTEGRAL TERM
# ============================================================

print("\n=== With Integral (reduces steady-state error) ===")
servo.set_pid(p=32, i=8, d=32)
test_response("P=32, I=8, D=32")

# ============================================================
# SPEED PID (STS only)
# ============================================================

if stype.has_speed_pid:
    print("\n=== Speed Loop PID (STS/SMS only) ===")
    
    # Read current speed PID
    sp = protocol.read(servo.id, stype.reg_speed_p, 1)[0]
    si = protocol.read(servo.id, stype.reg_speed_i, 1)[0]
    sd = protocol.read(servo.id, stype.reg_speed_d, 1)[0]
    print(f"Current Speed PID: P={sp}, I={si}, D={sd}")
    
    # The speed loop controls velocity, which affects smoothness
    # Higher speed P = faster acceleration
    # Speed I helps maintain constant velocity

# ============================================================
# PUNCH (MINIMUM PWM)
# ============================================================

print("\n=== Punch (Minimum PWM) ===")

# Read current punch
punch_data = protocol.read(servo.id, stype.reg_punch, 2)
punch = stype.unpack_word(punch_data)
print(f"Current punch: {punch}")

# Higher punch = stronger starting force, overcomes stiction
# Lower punch = gentler starts, may not overcome friction
print("Setting punch to 50...")
servo.set_punch(50)
test_response("Punch=50", test_moves=2)

print("Setting punch to 200...")
servo.set_punch(200)
test_response("Punch=200", test_moves=2)

# ============================================================
# MAX TORQUE
# ============================================================

print("\n=== Max Torque ===")

# Max torque limits how hard the servo can push
print("Testing with reduced torque (50%)...")
servo.set_max_torque(500)
test_response("Torque=500", test_moves=2)

print("Testing with full torque...")
servo.set_max_torque(1000)
test_response("Torque=1000", test_moves=2)

# ============================================================
# RESTORE DEFAULTS
# ============================================================

print("\n=== Restoring Balanced Settings ===")
servo.set_pid(p=32, i=0, d=32)
servo.set_punch(32)
servo.set_max_torque(1000)

# ============================================================
# CLEANUP
# ============================================================

servo.disable()
print("\nPID tuning demo complete!")
print("\nTips:")
print("- Start with low I (0) and adjust P/D first")
print("- Increase P for faster response")
print("- Increase D to reduce overshoot")
print("- Add small I only if needed for steady-state error")
print("- Adjust punch if servo struggles to start moving")


"""
Animated Move Example

Demonstrates S-curve motion profiles with jerk control
for smooth, professional-quality servo animation.
"""

from machine import UART, Pin
from feetech import ServoBus, Servo, Scheduler
import time

# ============================================================
# HARDWARE SETUP
# ============================================================

uart = UART(0, baudrate=1000000, tx=Pin(0), rx=Pin(1))
bus = ServoBus(uart)

print("Scanning for servos...")
found = bus.scan(start_id=1, end_id=10)
print(f"Found servos: {found}")

if not found:
    print("No servos found!")
    raise SystemExit

servo = Servo(bus, found[0])
servo.enable()

# ============================================================
# S-CURVE ANIMATED MOVES
# ============================================================

print("\n=== S-Curve Animation Demo ===\n")

# Read current position
start_pos = servo.read_position()
center = servo.servo_type.resolution // 2

# Move to start position
servo.move_to(100)
bus.execute()
time.sleep(1)

# Create scheduler for frame-rate control
scheduler = Scheduler(bus, fps=30)

print("Jerk = 0.5 (very smooth, slow response)")
servo.move_to(center, duration_ms=1000, jerk=0.5)
scheduler.run_until_complete()
time.sleep(0.5)

print("Jerk = 1.0 (balanced)")
servo.move_to(100, duration_ms=1000, jerk=1.0)
scheduler.run_until_complete()
time.sleep(0.5)

print("Jerk = 3.0 (snappy)")
servo.move_to(center, duration_ms=1000, jerk=3.0)
scheduler.run_until_complete()
time.sleep(0.5)

print("Jerk = 10.0 (very snappy, near-trapezoidal)")
servo.move_to(100, duration_ms=1000, jerk=10.0)
scheduler.run_until_complete()
time.sleep(0.5)

# ============================================================
# MOTION QUEUE DEMO
# ============================================================

print("\n=== Motion Queue Demo ===\n")
print("Queueing 5 moves in sequence...")

# Queue multiple moves (they'll execute one after another)
max_pos = servo.servo_type.resolution - 100

bus.queue_move(servo.id, center, 300, jerk=2.0)      # Move 1
bus.queue_move(servo.id, 100, 300, jerk=2.0)         # Move 2
bus.queue_move(servo.id, max_pos, 500, jerk=1.0)     # Move 3
bus.queue_move(servo.id, center, 500, jerk=1.0)      # Move 4
bus.queue_move(servo.id, 100, 300, jerk=3.0)         # Move 5

print("Running queued moves...")
scheduler.run_until_complete()

# ============================================================
# DIFFERENT DURATIONS
# ============================================================

print("\n=== Duration Demo ===\n")

print("Fast move (200ms)")
servo.move_to(max_pos, duration_ms=200, jerk=2.0)
scheduler.run_until_complete()
time.sleep(0.5)

print("Medium move (500ms)")
servo.move_to(100, duration_ms=500, jerk=2.0)
scheduler.run_until_complete()
time.sleep(0.5)

print("Slow move (2000ms)")
servo.move_to(center, duration_ms=2000, jerk=1.0)
scheduler.run_until_complete()

# ============================================================
# CLEANUP
# ============================================================

servo.disable()
print("\nDone!")


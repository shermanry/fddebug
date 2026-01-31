"""
Multi-Servo Control Example

Demonstrates controlling multiple servos simultaneously
using sync_write for maximum efficiency.
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
found = bus.scan(start_id=1, end_id=16)
print(f"Found {len(found)} servos: {found}")

if len(found) < 2:
    print("Need at least 2 servos for multi-servo demo")
    # Continue anyway for single servo testing

# Create Servo objects
servos = [Servo(bus, id) for id in found]

# Enable all torque
bus.set_all_torque(True)
print("All servos enabled")

# ============================================================
# SYNC_WRITE DEMO - Move all at once
# ============================================================

print("\n=== Sync Write Demo ===\n")
print("Moving all servos to position 500...")

# Queue positions for all servos
for s in servos:
    bus.set_position(s.id, 500)

# Execute all at once with single sync_write packet
bus.execute()
time.sleep(1)

print("Moving all servos to position 2000...")
for s in servos:
    bus.set_position(s.id, 2000)
bus.execute()
time.sleep(1)

# ============================================================
# COORDINATED ANIMATION
# ============================================================

print("\n=== Coordinated Animation ===\n")

scheduler = Scheduler(bus, fps=30)

# All servos move together to same position
print("All servos moving together...")
positions = {s.id: 1000 for s in servos}
scheduler.animate(positions, duration_ms=500, jerk=2.0)
scheduler.run_until_complete()
time.sleep(0.5)

# ============================================================
# STAGGERED ANIMATION
# ============================================================

print("\n=== Staggered Animation ===\n")

# Each servo moves to a different position
print("Staggered positions...")
positions = {}
for i, s in enumerate(servos):
    target = 500 + (i * 300)  # 500, 800, 1100, 1400, ...
    positions[s.id] = target

scheduler.animate(positions, duration_ms=800, jerk=1.5)
scheduler.run_until_complete()
time.sleep(0.5)

# ============================================================
# WAVE MOTION
# ============================================================

print("\n=== Wave Motion ===\n")

if len(servos) >= 2:
    print("Creating wave pattern...")
    
    # Manual wave animation
    center = servos[0].servo_type.resolution // 2
    amplitude = 500
    
    for cycle in range(3):
        for step in range(10):
            positions = {}
            for i, s in enumerate(servos):
                # Phase offset for each servo
                import math
                phase = (step / 10) + (i * 0.25)
                pos = int(center + amplitude * math.sin(phase * 2 * math.pi))
                positions[s.id] = pos
            
            scheduler.animate(positions, duration_ms=50, jerk=5.0)
            scheduler.run_until_complete()

# ============================================================
# INDIVIDUAL TIMING
# ============================================================

print("\n=== Different Durations ===\n")

if len(servos) >= 2:
    print("Each servo with different duration...")
    
    # First servo: fast move
    bus.queue_move(servos[0].id, 200, 300, jerk=3.0)
    
    # Second servo: slow move  
    if len(servos) > 1:
        bus.queue_move(servos[1].id, 3000, 1500, jerk=0.5)
    
    # Additional servos: medium moves
    for s in servos[2:]:
        bus.queue_move(s.id, 1500, 800, jerk=1.0)
    
    # Run all (they'll complete at different times)
    scheduler.run_until_complete()

# ============================================================
# READ ALL STATUS
# ============================================================

print("\n=== Status of All Servos ===\n")

for s in servos:
    status = s.read_status()
    print(f"Servo {s.id}: {status['angle']:.1f}° @ {status['voltage']:.1f}V, {status['temperature']}°C")

# ============================================================
# CLEANUP
# ============================================================

bus.set_all_torque(False)
print("\nAll servos disabled. Done!")


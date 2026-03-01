"""
Motion Interrupt Example

Demonstrates smooth motion interrupts - changing the target position
mid-animation while maintaining velocity continuity.

This is crucial for responsive robotics where commands can change
at any moment based on external input.
"""

from machine import UART, Pin
from feetech import ServoBus, Servo, Scheduler
import time

# Simulated external input (in real use, this would be from network, sensors, etc.)
_simulated_new_targets = [
    (300, 500),    # At 300ms, new target: 500
    (600, 3000),   # At 600ms, new target: 3000
    (1000, 1500),  # At 1000ms, new target: 1500
]

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
servo.enable()
print(f"Using servo {servo.id}, type: {servo.servo_type.name}")

scheduler = Scheduler(bus, fps=30)

# ============================================================
# EXAMPLE 1: Manual interrupt during non-blocking loop
# ============================================================

print("\n=== Example 1: Non-Blocking with Interrupts ===\n")

# Start a long animation
print("Starting 2-second move to position 4000...")
scheduler.animate({servo.id: 4000}, duration_ms=2000, jerk=1.0)

start_time = time.ticks_ms()
target_idx = 0

# Non-blocking animation loop
while scheduler.is_animating:
    # Process one frame
    scheduler.tick()
    
    # Check for simulated external input
    elapsed = time.ticks_diff(time.ticks_ms(), start_time)
    
    if target_idx < len(_simulated_new_targets):
        trigger_time, new_pos = _simulated_new_targets[target_idx]
        
        if elapsed >= trigger_time:
            print(f"  [{elapsed}ms] INTERRUPT! New target: {new_pos}")
            
            # Smooth interrupt - servo will blend to new trajectory
            scheduler.interrupt(servo.id, new_pos, 
                               duration_ms=300,  # 300ms to reach new target
                               jerk=2.0)         # Snappy response
            
            target_idx += 1
    
    # Maintain frame rate
    time.sleep_ms(scheduler.frame_ms)

print(f"Animation complete at position {servo.read_position()}")
time.sleep(0.5)

# ============================================================
# EXAMPLE 2: Compare with and without blending
# ============================================================

print("\n=== Example 2: Blended vs Abrupt Interrupt ===\n")

# Move to start position
servo.move_to(500)
bus.execute()
time.sleep(1)

# WITHOUT BLENDING (abrupt)
print("Without blending (abrupt interrupt):")
scheduler.animate({servo.id: 4000}, duration_ms=1000, jerk=1.0)

for _ in range(10):  # Run 10 frames (~333ms)
    scheduler.tick()
    time.sleep_ms(scheduler.frame_ms)

# Abrupt change - just clear and set new target
state = bus.get_servo(servo.id)
state.motion_queue.clear()
scheduler.animate({servo.id: 1000}, duration_ms=500, jerk=1.0)
print("  -> Abrupt change to 1000 (may see jerk)")

scheduler.run_until_complete()
time.sleep(1)

# Move to start position
servo.move_to(500)
bus.execute()
time.sleep(1)

# WITH BLENDING (smooth)
print("\nWith blending (smooth interrupt):")
scheduler.animate({servo.id: 4000}, duration_ms=1000, jerk=1.0)

for _ in range(10):  # Run 10 frames (~333ms)
    scheduler.tick()
    time.sleep_ms(scheduler.frame_ms)

# Smooth interrupt - maintains velocity
scheduler.interrupt(servo.id, 1000, duration_ms=500, jerk=2.0)
print("  -> Smooth blend to 1000 (velocity-continuous)")

scheduler.run_until_complete()
time.sleep(0.5)

# ============================================================
# EXAMPLE 3: Rapid target changes
# ============================================================

print("\n=== Example 3: Rapid Target Changes ===\n")

servo.move_to(2000)
bus.execute()
time.sleep(0.5)

# Simulate rapid input changes (like tracking a moving object)
print("Simulating rapid target tracking...")

targets = [500, 3500, 1000, 3000, 2000]
for target in targets:
    print(f"  -> New target: {target}")
    scheduler.interrupt(servo.id, target, duration_ms=200, jerk=3.0)
    
    # Run for 150ms before next change (don't wait for completion)
    for _ in range(5):
        scheduler.tick()
        time.sleep_ms(scheduler.frame_ms)

# Let final motion complete
scheduler.run_until_complete()
print(f"Final position: {servo.read_position()}")

# ============================================================
# EXAMPLE 4: Using redirect() with arrival time
# ============================================================

print("\n=== Example 4: Redirect with Arrival Time ===\n")

servo.move_to(1000)
bus.execute()
time.sleep(0.5)

scheduler.animate({servo.id: 4000}, duration_ms=2000, jerk=1.0)

# After 500ms, redirect to arrive at new position
for _ in range(15):
    scheduler.tick()
    time.sleep_ms(scheduler.frame_ms)

print("Redirecting to 2000, arrive in 500ms...")
scheduler.redirect(servo.id, 2000, arrival_time_ms=500, jerk=1.5)

scheduler.run_until_complete()

# ============================================================
# CLEANUP
# ============================================================

servo.disable()
print("\nDone! Motion interrupts enable responsive, smooth control.")
print("Key takeaways:")
print("  1. Use tick() in a loop for non-blocking animation")
print("  2. Call interrupt() to smoothly change targets mid-motion")
print("  3. Higher jerk = faster response to interrupts")
print("  4. Velocity blending prevents jerky motion on trajectory changes")


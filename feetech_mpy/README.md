# Feetech Servo Library for MicroPython

A high-performance, modular library for controlling Feetech SCS and STS series servos on RP2040 and other MicroPython-compatible microcontrollers.

## Features

- **Servo Support**: SCS0009, STS3215, and other Feetech servo series
- **Automatic Endianness**: Handles SCS (big-endian) and STS (little-endian) automatically
- **Async Batch Commands**: Queue commands for multiple servos, send with single sync_write
- **S-Curve Motion Profiles**: Smooth animation with configurable jerk control
- **Frame-Rate Animation**: 30+ FPS scheduling for synchronized multi-servo motion
- **Motion Queue**: Chain moves for continuous animation sequences

## Hardware

### Tested Configurations

| Microcontroller | Adapter | Status |
|-----------------|---------|--------|
| WIZnet RP2040 | Waveshare Bus Servo Adapter v1.1 | ✅ |
| Raspberry Pi Pico | Waveshare Bus Servo Adapter | ✅ |
| RP2040 | URT-1 Debugger | ✅ |

### Wiring

Connect the Waveshare adapter to your RP2040:

| Adapter | RP2040 |
|---------|--------|
| TX | GP1 (UART0 RX) |
| RX | GP0 (UART0 TX) |
| GND | GND |
| VCC | 5V (for adapter logic) |

**Note**: Servos need separate 6-8V power supply!

## Installation

Copy the `feetech` folder to your device's `/lib/` directory:

```bash
# Using mpremote
mpremote cp -r feetech :lib/
```

Or copy files manually using Thonny or your preferred IDE.

## Quick Start

```python
from machine import UART, Pin
from feetech import ServoBus, Servo, Scheduler

# Initialize UART at 1Mbaud
uart = UART(0, baudrate=1000000, tx=Pin(0), rx=Pin(1))

# Create bus and scan for servos
bus = ServoBus(uart)
found = bus.scan()
print(f"Found servos: {found}")

# Create servo controller
servo = Servo(bus, found[0])
servo.enable()

# Simple position move
servo.move_to(2048)
bus.execute()

# Animated S-curve move (smooth!)
servo.move_to(1000, duration_ms=500, jerk=1.0)

# Run animation at 30 FPS
scheduler = Scheduler(bus, fps=30)
scheduler.run_until_complete()
```

## S-Curve Motion with Jerk Control

The library provides smooth S-curve motion profiles with configurable jerk:

```python
# Jerk controls motion smoothness
# Low jerk (0.1-0.5) = Very smooth, slow response
# Medium jerk (1.0-2.0) = Balanced (recommended)
# High jerk (3.0-10.0) = Snappy, quick response

servo.move_to(2048, duration_ms=500, jerk=1.5)
scheduler.run_until_complete()
```

## Multi-Servo Animation

Animate multiple servos simultaneously with sync_write:

```python
# Queue moves for all servos
bus.queue_move(1, 2048, duration_ms=500, jerk=1.5)
bus.queue_move(2, 1024, duration_ms=500, jerk=1.5)
bus.queue_move(3, 3072, duration_ms=500, jerk=1.5)

# All servos move together, completing at same time
scheduler.run_until_complete()
```

Or use the scheduler's animate method:

```python
scheduler.animate({
    1: 2048,
    2: 1024,
    3: 3072,
}, duration_ms=500, jerk=1.5)

scheduler.run_until_complete()
```

## Motion Interrupts (Smooth Trajectory Changes)

The library supports smooth motion interrupts - changing the target position
mid-animation while maintaining velocity continuity:

```python
# Blocking mode (no interrupts possible)
scheduler.animate({1: 2048}, duration_ms=1000)
scheduler.run_until_complete()  # Blocks until done

# Non-blocking mode (allows interrupts)
scheduler.animate({1: 2048}, duration_ms=1000)

while scheduler.is_animating:
    scheduler.tick()  # Process one frame
    
    # Check for new input from external source
    if new_target_received:
        # Smooth interrupt! Servo blends to new trajectory
        scheduler.interrupt(1, new_position, duration_ms=300, jerk=2.0)
    
    time.sleep_ms(scheduler.frame_ms)
```

The `interrupt()` method:
1. Estimates current position and velocity
2. Creates a new blended trajectory from current state
3. Uses Hermite spline interpolation for velocity continuity
4. No jerky motion on trajectory changes!

```python
# Interrupt single servo
scheduler.interrupt(servo_id, new_position, duration_ms=300, jerk=2.0)

# Interrupt all servos
scheduler.interrupt_all({1: 500, 2: 1500}, duration_ms=300, jerk=2.0)

# Redirect with arrival time (calculates duration automatically)
scheduler.redirect(servo_id, new_position, arrival_time_ms=500)
```

## API Reference

### ServoBus

Main bus controller for multi-servo management.

```python
bus = ServoBus(uart, baud=1000000, timeout_ms=10)

bus.scan(start_id=1, end_id=20)      # Scan for servos
bus.set_position(id, position)        # Queue position command
bus.set_all_positions({1: 100, 2: 200})  # Queue multiple
bus.execute()                         # Send all queued commands

bus.queue_move(id, pos, duration_ms, jerk)  # Queue animated move
bus.queue_all_moves(positions, duration_ms, jerk)

bus.set_torque(id, True/False)        # Enable/disable torque
bus.set_all_torque(True/False)        # All servos at once

bus.read_position(id)                 # Read current position
bus.read_status(id)                   # Read full status dict
```

### Servo

High-level individual servo control.

```python
servo = Servo(bus, servo_id)

# Motion
servo.move_to(position, duration_ms=None, speed=None, jerk=1.0)
servo.move_to_angle(degrees, duration_ms=None, jerk=1.0)
servo.move_by(delta, duration_ms=None, jerk=1.0)
servo.stop()

# Torque
servo.enable()
servo.disable()

# Feedback
servo.read_position()      # Returns int (ticks)
servo.read_status()        # Returns dict
servo.position             # Cached position
servo.angle                # Cached angle (degrees)

# Configuration
servo.set_pid(p=32, i=0, d=32)
servo.set_speed_pid(p=50, i=10, d=5)  # STS only
servo.set_punch(32)
servo.set_max_torque(1000)
servo.set_angle_limits(min_angle=0, max_angle=300)
servo.set_mode(Mode.POSITION)  # STS only
servo.set_acceleration(50)     # STS only

# EPROM (persistent settings)
servo.set_id(new_id)
servo.set_baud_rate(1000000)
servo.calibrate_offset()  # STS only

# Step Mode (STS only - Mode 3)
servo.enable_step_mode(speed=300, acc=50)
servo.step(500)    # Move 500 steps forward
servo.step(500)    # Move 500 more steps forward  
servo.step(-1000)  # Move 1000 steps backward
servo.set_step_speed(200)  # Change speed
servo.disable_step_mode()  # Return to normal mode
```

### Step Mode (Incremental Multi-turn)

Step mode (Mode 3) enables incremental position control for multi-turn applications.
Unlike normal servo mode, the goal position is a **delta** (how much to move), not an absolute position.

```python
from feetech import Servo

servo = Servo(bus, 1)

# Enable step mode (sets mode=3, limits=0,0)
servo.enable_step_mode(speed=300, acc=50)

# Each step() call moves the servo by that amount
servo.step(500)    # Move 500 steps forward
servo.step(500)    # Move 500 more (cumulative: 1000)
servo.step(-1000)  # Move 1000 steps back (returns to start)

# Full rotation (4096 steps = 360°)
servo.step(4096)   # One full rotation forward
servo.step(-4096)  # One full rotation back

# Return to normal servo mode
servo.disable_step_mode()
```

**Important notes:**
- Uses sign-magnitude encoding (bit 15 = direction)
- Limits must be 0,0 for step mode to work
- Position feedback may not be reliable in step mode
- Only available on STS/SMS servos

### Scheduler

Frame-rate controlled animation with motion interrupt support.

```python
scheduler = Scheduler(bus, fps=30)

# Animation control
scheduler.animate(positions_dict, duration_ms, jerk)
scheduler.animate_degrees(angles_dict, duration_ms, jerk)

# Run modes
scheduler.tick()                      # Single frame (non-blocking)
scheduler.run()                       # Continuous loop
scheduler.run_until_complete()        # Until animations done (blocking)
scheduler.run_frames(count)           # Fixed number of frames
scheduler.stop()

# Motion interrupts (smooth trajectory changes)
scheduler.interrupt(id, pos, duration_ms, jerk)  # Blend to new target
scheduler.interrupt_all(positions, duration_ms)   # Interrupt multiple
scheduler.redirect(id, pos, arrival_time_ms)      # Redirect with timing

# Properties
scheduler.is_animating                # True if motions active
scheduler.frame_ms                    # Frame duration in ms

# Callbacks
scheduler.on_frame(callback)          # Called each frame
scheduler.on_complete(callback)       # Called when done
```

### Motion Profiles

```python
from feetech import SCurveProfile, create_scurve_move

# Create a motion profile
profile = create_scurve_move(start=0, end=2048, duration_ms=500, jerk=1.5)

# Manual position interpolation
profile.start()
while not profile.is_complete():
    pos = profile.current_position()
    # ... use position
```

## Servo Types

| Series | Endian | Resolution | Angle Range | Multi-turn | Mode Switch |
|--------|--------|------------|-------------|------------|-------------|
| SCS | Big | 1024 | 300° | ❌ | ❌ |
| STS | Little | 4096 | 360° | ✅ | ✅ |
| SMS | Little | 4096 | 360° | ✅ | ✅ |

The library automatically detects servo type and handles differences.

## Performance Tips

1. **Use sync_write**: Queue commands with `set_position()` or `queue_move()`, then call `execute()` once. This sends all positions in one packet.

2. **Target 30 FPS**: Higher frame rates consume more CPU and bus bandwidth with diminishing returns.

3. **Let servos handle high-frequency control**: The servo's internal controller runs much faster than your animation loop. Use hardware speed/acceleration when possible.

4. **Pre-compute animations**: For complex sequences, calculate positions ahead of time.

5. **Minimize reads**: Reading feedback is slower than writing. Read status only when needed.

## Examples

See the `examples/` folder:
- `basic_position.py` - Simple position control
- `animated_move.py` - S-curve animation demo
- `multi_servo.py` - Coordinated multi-servo control
- `pid_tuning.py` - PID parameter adjustment
- `motion_interrupt.py` - Smooth trajectory changes mid-motion

## License

MIT License


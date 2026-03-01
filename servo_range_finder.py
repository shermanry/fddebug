#!/usr/bin/env python3
"""
servo_range_finder.py - Automatic Servo Range Calibration (Desktop Version)

Checks EPROM limits first - if already set by assembler, uses those.
Set override=True to recalibrate and find physical limits by monitoring load.

Results are printed and can be used to set software limits.

Usage:
    python servo_range_finder.py [--override] [--servo ID,ID,...] [--port PORT]
"""

import time
import argparse
import serial.tools.list_ports
from feetech_servo import FeetechServo, SCSReg, SMSReg, get_servo_type

# Calibration parameters
LOAD_THRESHOLD = 100       # Load limit (0-1023, 100 = ~10% of max)
STEP_SIZE = 10             # Position step per iteration  
STEP_DELAY_MS = 50         # Delay between steps (ms)
BACKOFF_STEPS = 3          # Steps to back off when limit hit
SETTLE_DELAY_MS = 100      # Delay after moving to let load settle


def read_servo_mode(servo, servo_id: int, servo_type: str) -> int:
    """Read servo operating mode."""
    try:
        type_class = get_servo_type(servo_type)
        if not type_class.supports_mode:
            return 0  # SCS doesn't have mode register
        mode = servo.read_byte(servo_id, SMSReg.MODE)
        return mode if mode >= 0 else 0
    except Exception:
        return -1


def is_multi_turn(servo, servo_id: int, servo_type: str) -> bool:
    """Check if servo is in multi-turn/step mode (Mode 3)."""
    return read_servo_mode(servo, servo_id, servo_type) == 3


def read_eprom_limits(servo, servo_id: int, servo_type: str) -> dict:
    """
    Read angle limits from servo EPROM.
    
    Returns:
        dict with 'min', 'max', 'has_limits', 'is_multi_turn'
    """
    try:
        type_class = get_servo_type(servo_type)
        resolution = type_class.max_position + 1  # 4096 for STS, 1024 for SCS
        
        # Configure for correct endianness
        servo.configure_for_type(servo_type)
        
        # Check mode (STS only)
        mode = read_servo_mode(servo, servo_id, servo_type)
        multi_turn = (mode == 3)
        
        # Read limits with correct signed/unsigned handling
        if type_class.supports_multi_turn:
            min_val = servo.read_word_signed(servo_id, SCSReg.MIN_ANGLE_LIMIT_L)
            max_val = servo.read_word_signed(servo_id, SCSReg.MAX_ANGLE_LIMIT_L)
        else:
            min_val = servo.read_word(servo_id, SCSReg.MIN_ANGLE_LIMIT_L)
            max_val = servo.read_word(servo_id, SCSReg.MAX_ANGLE_LIMIT_L)
        
        # Check if limits are set (not full range)
        full_range = resolution - 1
        has_limits = not (min_val == 0 and max_val == full_range)
        
        # Multi-turn servos have 0,0 limits by design
        if multi_turn and min_val == 0 and max_val == 0:
            has_limits = False
        
        return {
            'min': min_val,
            'max': max_val,
            'center': (min_val + max_val) // 2,
            'range': max_val - min_val,
            'has_limits': has_limits,
            'is_multi_turn': multi_turn,
            'mode': mode,
            'source': 'eprom',
            'resolution': resolution,
            'servo_type': servo_type,
        }
    except Exception as e:
        print(f"  [{servo_id}] Error reading EPROM limits: {e}")
        return None


def read_load(servo, servo_id: int) -> int:
    """Read current load magnitude from servo (0-1023)."""
    load_raw = servo.read_load(servo_id)
    if load_raw < 0:
        return 0
    # Load uses bit 10 for direction, bits 0-9 for magnitude
    return load_raw & 0x3FF


def find_limit(servo, servo_id: int, servo_type: str, direction: int, start_pos: int) -> tuple:
    """
    Find limit in given direction.
    
    Args:
        servo: FeetechServo instance
        servo_id: Servo ID
        servo_type: 'scs' or 'sts'
        direction: -1 for min, +1 for max
        start_pos: Starting position
    
    Returns:
        (limit_position, hit_limit) - position and whether we hit a physical limit
    """
    dir_name = "MIN" if direction < 0 else "MAX"
    print(f"  [{servo_id}] Finding {dir_name} limit from position {start_pos}...")
    
    type_class = get_servo_type(servo_type)
    hw_min = 0
    hw_max = type_class.max_position
    
    print(f"  [{servo_id}] Hardware range: {hw_min}-{hw_max} ({servo_type.upper()})")
    
    current_pos = start_pos
    last_safe_pos = start_pos
    
    # Wait for load to settle
    time.sleep(SETTLE_DELAY_MS * 3 / 1000)
    initial_load = read_load(servo, servo_id)
    print(f"  [{servo_id}] Initial load: {initial_load}")
    
    while True:
        # Calculate next position
        next_pos = current_pos + (direction * STEP_SIZE)
        
        # Check hardware bounds
        if next_pos < hw_min or next_pos > hw_max:
            print(f"  [{servo_id}] Reached hardware limit at {current_pos}")
            return current_pos, False
        
        # Move to next position
        servo.write_position(servo_id, next_pos, speed=500)
        time.sleep(STEP_DELAY_MS / 1000)
        
        # Wait for servo to settle
        time.sleep(SETTLE_DELAY_MS / 1000)
        
        # Read actual position and load
        actual_pos = servo.read_position(servo_id)
        load = read_load(servo, servo_id)
        
        # Check if servo actually moved (stall detection)
        pos_error = abs(actual_pos - next_pos)
        if pos_error > STEP_SIZE * 3:  # Servo isn't reaching target
            print(f"  [{servo_id}] Stall detected! Target={next_pos}, Actual={actual_pos}, Load={load}")
            
            # Back off to last safe position
            safe_pos = last_safe_pos - (direction * STEP_SIZE * BACKOFF_STEPS)
            safe_pos = max(hw_min, min(hw_max, safe_pos))
            
            print(f"  [{servo_id}] Backing off to {safe_pos}")
            servo.write_position(servo_id, safe_pos, speed=500)
            time.sleep(SETTLE_DELAY_MS * 2 / 1000)
            
            return last_safe_pos, True
        
        if load > LOAD_THRESHOLD:
            print(f"  [{servo_id}] Load limit hit! Load={load} at pos={next_pos}")
            
            # Back off to last safe position
            safe_pos = last_safe_pos - (direction * STEP_SIZE * BACKOFF_STEPS)
            safe_pos = max(hw_min, min(hw_max, safe_pos))
            
            print(f"  [{servo_id}] Backing off to {safe_pos}")
            servo.write_position(servo_id, safe_pos, speed=500)
            time.sleep(SETTLE_DELAY_MS * 2 / 1000)
            
            return last_safe_pos, True
        
        # Update positions
        last_safe_pos = current_pos
        current_pos = next_pos
        
        # Progress indicator every 50 steps
        steps_taken = abs(current_pos - start_pos) // STEP_SIZE
        if steps_taken % 50 == 0 and steps_taken > 0:
            print(f"  [{servo_id}] At position {current_pos}, load={load}")


def calibrate_servo(servo, servo_id: int, servo_type: str, override: bool = False) -> dict:
    """
    Calibrate a single servo to find its range.
    
    Args:
        servo: FeetechServo instance
        servo_id: Servo ID to calibrate
        servo_type: 'scs' or 'sts'
        override: If True, ignore EPROM limits and recalibrate.
    
    Returns:
        dict with calibration results or None if failed
    """
    print(f"\n[CALIBRATE] Checking servo {servo_id} ({servo_type.upper()})...")
    
    servo.configure_for_type(servo_type)
    
    # First check EPROM limits
    eprom = read_eprom_limits(servo, servo_id, servo_type)
    
    # Skip multi-turn servos
    if eprom and eprom.get('is_multi_turn'):
        print(f"  [{servo_id}] Multi-turn mode (Mode 3) - skipping calibration")
        print(f"  [{servo_id}] Use software limits instead")
        return {
            'id': servo_id,
            'is_multi_turn': True,
            'mode': eprom.get('mode', 3),
            'source': 'multi_turn',
            'skip': True,
            'servo_type': servo_type,
        }
    
    if eprom and eprom['has_limits'] and not override:
        print(f"  [{servo_id}] EPROM limits found: {eprom['min']} - {eprom['max']}")
        print(f"  [{servo_id}] Using EPROM limits (use --override to recalibrate)")
        
        # Move servo to center
        center = eprom['center']
        print(f"  [{servo_id}] Moving to center position: {center}")
        servo.enable_torque(servo_id, True)
        time.sleep(0.05)
        servo.write_position(servo_id, center, speed=500)
        time.sleep(0.3)
        
        eprom['id'] = servo_id
        eprom['hit_min'] = False
        eprom['hit_max'] = False
        return eprom
    
    if eprom and not eprom['has_limits']:
        print(f"  [{servo_id}] No EPROM limits set (full range)")
    elif override:
        print(f"  [{servo_id}] Override enabled - recalibrating...")
    
    print(f"[CALIBRATE] Starting physical calibration for servo {servo_id}")
    
    # Enable torque
    servo.enable_torque(servo_id, True)
    time.sleep(0.1)
    
    # Read current position
    start_pos = servo.read_position(servo_id)
    start_load = read_load(servo, servo_id)
    
    print(f"  [{servo_id}] Starting position: {start_pos}, load: {start_load}")
    
    # Verify servo can move by doing a small test move
    test_target = start_pos + 20 if start_pos < 500 else start_pos - 20
    servo.write_position(servo_id, test_target, speed=500)
    time.sleep(0.3)
    test_actual = servo.read_position(servo_id)
    test_error = abs(test_actual - test_target)
    
    if test_error > 30:
        print(f"  [{servo_id}] ERROR: Servo not responding to commands!")
        print(f"  [{servo_id}]   Target: {test_target}, Actual: {test_actual}")
        return None
    
    # Return to start
    servo.write_position(servo_id, start_pos, speed=500)
    time.sleep(0.3)
    
    print(f"  [{servo_id}] Movement verified OK")
    
    if start_load > LOAD_THRESHOLD:
        print(f"  [{servo_id}] WARNING: Starting load is already high!")
    
    # Find minimum
    min_pos, hit_min = find_limit(servo, servo_id, servo_type, -1, start_pos)
    
    # Return to start
    print(f"  [{servo_id}] Returning to start position ({start_pos})...")
    servo.write_position(servo_id, start_pos, speed=500)
    time.sleep(1.0)
    
    # Find maximum
    max_pos, hit_max = find_limit(servo, servo_id, servo_type, +1, start_pos)
    
    # Return to start
    servo.write_position(servo_id, start_pos, speed=500)
    time.sleep(0.2)
    
    result = {
        'id': servo_id,
        'min': min_pos,
        'max': max_pos,
        'center': (min_pos + max_pos) // 2,
        'range': max_pos - min_pos,
        'hit_min': hit_min,
        'hit_max': hit_max,
        'source': 'calibrated',
        'servo_type': servo_type,
    }
    
    print(f"\n  [{servo_id}] RESULTS:")
    print(f"    Min: {min_pos} {'(physical limit)' if hit_min else '(hw limit)'}")
    print(f"    Max: {max_pos} {'(physical limit)' if hit_max else '(hw limit)'}")
    print(f"    Range: {result['range']} ticks")
    print(f"    Center: {result['center']}")
    
    return result


def run(port: str = None, override: bool = False, servo_ids: list = None):
    """
    Main calibration routine.
    
    Args:
        port: Serial port (auto-detect if None)
        override: If True, recalibrate ignoring EPROM limits
        servo_ids: Optional list of specific servo IDs
    """
    print("[RANGE_FINDER] Servo Range Calibration Tool")
    print(f"  Load threshold: {LOAD_THRESHOLD} ({LOAD_THRESHOLD/10.23:.1f}%)")
    print(f"  Step size: {STEP_SIZE}")
    print(f"  Override EPROM: {override}")
    print()
    
    # Create servo controller
    servo = FeetechServo()
    
    # Find and open port
    if port is None:
        # Find USB serial ports
        ports = []
        for p in serial.tools.list_ports.comports():
            if 'usbserial' in p.device or 'usbmodem' in p.device or 'ttyUSB' in p.device:
                ports.append(p.device)
        if not ports:
            print("[RANGE_FINDER] No USB serial ports found!")
            return {}
        port = ports[0]
        print(f"[RANGE_FINDER] Auto-detected port: {port}")
    
    if not servo.open(port):
        print(f"[RANGE_FINDER] Failed to open port {port}")
        return {}
    
    print(f"[RANGE_FINDER] Opened {port}")
    
    # Scan for servos
    if servo_ids:
        found = []
        servo_types = {}
        for sid in servo_ids:
            if servo.ping(sid) >= 0:  # ping returns -1 on failure
                found.append(sid)
                servo_types[sid] = servo.detect_type(sid)
        print(f"[RANGE_FINDER] Using specified servos: {found}")
    else:
        print("[RANGE_FINDER] Scanning for servos (1-30)...")
        found = []
        servo_types = {}
        for sid in range(1, 31):
            if servo.ping(sid) >= 0:  # ping returns -1 on failure
                found.append(sid)
                servo_types[sid] = servo.detect_type(sid)
                print(f"  Found servo {sid} ({servo_types[sid].upper()})")
    
    if not found:
        print("[RANGE_FINDER] No servos found!")
        servo.close()
        return {}
    
    print(f"\n[RANGE_FINDER] Found {len(found)} servo(s): {found}")
    
    # Calibrate each servo
    results = {}
    for servo_id in found:
        try:
            servo_type = servo_types.get(servo_id, 'sts')
            result = calibrate_servo(servo, servo_id, servo_type, override=override)
            if result:
                results[servo_id] = result
        except Exception as e:
            print(f"[RANGE_FINDER] Error calibrating servo {servo_id}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    print("\n" + "=" * 60)
    print("[RANGE_FINDER] CALIBRATION COMPLETE")
    print("=" * 60)
    
    for servo_id, result in results.items():
        if result.get('skip'):
            print(f"\nServo {servo_id}: MULTI-TURN (uses software limits)")
            continue
        source = result.get('source', 'unknown')
        stype = result.get('servo_type', 'sts').upper()
        print(f"\nServo {servo_id} ({stype}, {source}):")
        print(f"  Range: {result['min']} - {result['max']} ({result['range']} ticks)")
        print(f"  Safe center: {result['center']}")
    
    # Print as config format
    print("\n# Python config format:")
    print("SERVO_LIMITS = {")
    for servo_id, result in results.items():
        if result.get('skip'):
            print(f"    # {servo_id}: MULTI-TURN (software limits)")
            continue
        source = result.get('source', '')
        stype = result.get('servo_type', 'sts').upper()
        print(f"    {servo_id}: {{'min': {result['min']}, 'max': {result['max']}, 'center': {result['center']}}},  # {stype} {source}")
    print("}")
    
    # Disable servos
    print("\n[RANGE_FINDER] Disabling servos...")
    for servo_id in found:
        try:
            servo.enable_torque(servo_id, False)
        except:
            pass
    
    servo.close()
    print("[RANGE_FINDER] Done!")
    return results


def sweep(port: str = None, servo_ids: list = None, cycles: int = 3, move_time: int = 1000):
    """
    Simultaneous sweep of all servos between their min/max limits.
    Uses the limits from a previous calibration run.
    """
    print("[SWEEP] Simultaneous Servo Sweep Test")
    print(f"  Cycles: {cycles}")
    print(f"  Move time: {move_time}ms")
    print()
    
    # These are the limits from the last calibration - update as needed
    SERVO_LIMITS = {
        20: {'min': 763, 'max': 873, 'center': 818},
        21: {'min': 771, 'max': 851, 'center': 811},
        22: {'min': 497, 'max': 587, 'center': 542},
        23: {'min': 618, 'max': 758, 'center': 688},
        24: {'min': 454, 'max': 544, 'center': 499},
        25: {'min': 479, 'max': 559, 'center': 519},
    }
    
    servo = FeetechServo()
    
    # Find and open port
    if port is None:
        ports = []
        for p in serial.tools.list_ports.comports():
            if 'usbserial' in p.device or 'usbmodem' in p.device or 'ttyUSB' in p.device:
                ports.append(p.device)
        if not ports:
            print("[SWEEP] No USB serial ports found!")
            return
        port = ports[0]
        print(f"[SWEEP] Auto-detected port: {port}")
    
    if not servo.open(port):
        print(f"[SWEEP] Failed to open port {port}")
        return
    
    print(f"[SWEEP] Opened {port}")
    
    # Use provided servo IDs or all from SERVO_LIMITS
    if servo_ids:
        ids_to_sweep = [sid for sid in servo_ids if sid in SERVO_LIMITS]
    else:
        ids_to_sweep = list(SERVO_LIMITS.keys())
    
    if not ids_to_sweep:
        print("[SWEEP] No servos to sweep!")
        servo.close()
        return
    
    print(f"[SWEEP] Sweeping servos: {ids_to_sweep}")
    
    # Configure for SCS servos (big-endian, 10-bit)
    servo.configure_for_type('scs')
    
    # Enable torque on all servos
    print("[SWEEP] Enabling torque...")
    for sid in ids_to_sweep:
        servo.enable_torque(sid, True)
    time.sleep(0.2)
    
    # Track current positions for smooth interpolation
    current_positions = {sid: SERVO_LIMITS[sid]['center'] for sid in ids_to_sweep}
    
    def move_all_smooth(target_positions, steps=20):
        """Move all servos smoothly using interpolation"""
        for step in range(steps):
            t = (step + 1) / steps  # 0.05, 0.10, ... 1.0
            # Ease-in-out interpolation for smoother motion
            t_smooth = t * t * (3 - 2 * t)  # Smoothstep
            
            commands = []
            for sid in ids_to_sweep:
                start = current_positions[sid]
                end = target_positions[sid]
                pos = int(start + (end - start) * t_smooth)
                commands.append((sid, pos, 0, 0))  # Immediate move
            
            servo.sync_write_position(commands)
            time.sleep(move_time / 1000 / steps)
        
        # Update current positions
        for sid in ids_to_sweep:
            current_positions[sid] = target_positions[sid]
    
    def move_all_instant(positions_dict):
        """Move all servos instantly (for quick moves)"""
        commands = []
        for sid in ids_to_sweep:
            pos = positions_dict[sid]
            commands.append((sid, pos, 0, 0))
        servo.sync_write_position(commands)
        for sid in ids_to_sweep:
            current_positions[sid] = positions_dict[sid]
    
    print(f"[SWEEP] Movement time: {move_time}ms per move (smooth interpolation)")
    
    # Move all to center first
    print("[SWEEP] Moving all to center...")
    centers = {sid: SERVO_LIMITS[sid]['center'] for sid in ids_to_sweep}
    move_all_instant(centers)
    time.sleep(1.0)
    
    try:
        for cycle in range(cycles):
            print(f"\n[SWEEP] Cycle {cycle + 1}/{cycles}")
            
            # Sweep to MIN
            print("  -> Moving to MIN...")
            mins = {sid: SERVO_LIMITS[sid]['min'] for sid in ids_to_sweep}
            move_all_smooth(mins)
            time.sleep(0.5)  # Brief pause after smooth move
            
            # Read positions (use big-endian for SCS)
            for sid in ids_to_sweep:
                limits = SERVO_LIMITS[sid]
                try:
                    time.sleep(0.02)  # Small delay between reads
                    raw = servo.read_bytes(sid, 56, 2)  # PRESENT_POSITION_L/H
                    if raw:
                        pos = (raw[0] << 8) | raw[1]  # SCS is big-endian
                        error = abs(pos - limits['min'])
                        status = "OK" if error < 30 else f"off by {error}"
                        print(f"    Servo {sid}: pos={pos} (target={limits['min']}) {status}")
                    else:
                        print(f"    Servo {sid}: no response")
                except Exception as e:
                    print(f"    Servo {sid}: read error")
            
            time.sleep(1.0)
            
            # Sweep to MAX
            print("  -> Moving to MAX...")
            maxs = {sid: SERVO_LIMITS[sid]['max'] for sid in ids_to_sweep}
            move_all_smooth(maxs)
            time.sleep(0.5)  # Brief pause after smooth move
            
            # Read positions (use big-endian for SCS)
            for sid in ids_to_sweep:
                limits = SERVO_LIMITS[sid]
                try:
                    time.sleep(0.02)  # Small delay between reads
                    raw = servo.read_bytes(sid, 56, 2)  # PRESENT_POSITION_L/H
                    if raw:
                        pos = (raw[0] << 8) | raw[1]  # SCS is big-endian
                        error = abs(pos - limits['max'])
                        status = "OK" if error < 30 else f"off by {error}"
                        print(f"    Servo {sid}: pos={pos} (target={limits['max']}) {status}")
                    else:
                        print(f"    Servo {sid}: no response")
                except Exception as e:
                    print(f"    Servo {sid}: read error")
            
            time.sleep(1.0)
            
            # Sweep to CENTER
            print("  -> Moving to CENTER...")
            move_all_smooth(centers)
            time.sleep(0.5)
        
        print("\n[SWEEP] Complete!")
        
    except KeyboardInterrupt:
        print("\n[SWEEP] Interrupted!")
    
    # Disable torque
    print("[SWEEP] Disabling torque...")
    for sid in ids_to_sweep:
        servo.enable_torque(sid, False)
    
    servo.close()
    print("[SWEEP] Done!")


def main():
    global LOAD_THRESHOLD, STEP_SIZE
    
    parser = argparse.ArgumentParser(description='Servo Range Calibration Tool')
    parser.add_argument('--override', action='store_true',
                        help='Ignore EPROM limits and recalibrate')
    parser.add_argument('--sweep', action='store_true',
                        help='Run simultaneous sweep test using calibrated limits')
    parser.add_argument('--cycles', type=int, default=3,
                        help='Number of sweep cycles (default: 3)')
    parser.add_argument('--time', type=int, default=1000,
                        help='Movement time in ms (default: 1000)')
    parser.add_argument('--servo', type=str, default=None,
                        help='Comma-separated list of servo IDs (e.g., 1,2,3)')
    parser.add_argument('--port', type=str, default=None,
                        help='Serial port (auto-detect if not specified)')
    parser.add_argument('--threshold', type=int, default=100,
                        help='Load threshold for limit detection (default: 100)')
    parser.add_argument('--step', type=int, default=10,
                        help='Position step size (default: 10)')
    
    args = parser.parse_args()
    
    # Parse servo IDs
    servo_ids = None
    if args.servo:
        servo_ids = [int(x.strip()) for x in args.servo.split(',')]
    
    if args.sweep:
        sweep(port=args.port, servo_ids=servo_ids, cycles=args.cycles, move_time=args.time)
    else:
        # Update globals from args
        LOAD_THRESHOLD = args.threshold
        STEP_SIZE = args.step
        run(port=args.port, override=args.override, servo_ids=servo_ids)


if __name__ == "__main__":
    main()


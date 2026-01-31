"""
Servo Bus Manager

High-level interface for managing multiple servos on a single bus.
Designed for async operation where commands are queued and then
sent together for maximum efficiency.

Key Features:
- Queue position commands for any/all servos
- Execute all pending commands with a single sync_write
- Frame-rate controlled update loop
- Automatic servo type detection
- Motion queue integration

Usage:
    bus = ServoBus(uart)
    bus.scan()  # Find connected servos
    
    # Queue commands (non-blocking)
    bus.set_position(1, 2048)
    bus.set_position(2, 1024)
    bus.set_position(3, 3072)
    
    # Execute all at once
    bus.execute()  # Single sync_write packet
"""

import time
from .protocol import Protocol, BROADCAST_ID
from .servo_types import ServoType, STSType, SCSType, detect_servo_type
from .registers import SMSReg
from .motion import MotionQueue, SCurveProfile, create_scurve_move


class ServoState:
    """
    Tracks the state and pending commands for a single servo.
    """
    
    __slots__ = (
        'id', 'servo_type', 'enabled',
        'current_position', 'target_position',
        'current_speed', 'target_speed',
        'current_load', 'voltage', 'temperature',
        'pending_position', 'pending_speed', 'pending_time',
        'motion_queue', 'last_update'
    )
    
    def __init__(self, servo_id: int, servo_type: type = STSType):
        self.id = servo_id
        self.servo_type = servo_type
        self.enabled = True
        
        # Current state (from feedback)
        self.current_position = 0
        self.current_speed = 0
        self.current_load = 0
        self.voltage = 0
        self.temperature = 0
        
        # Target state
        self.target_position = 0
        self.target_speed = 0
        
        # Pending command (queued for next execute())
        self.pending_position = None
        self.pending_speed = None
        self.pending_time = None
        
        # Motion queue for animated moves
        self.motion_queue = MotionQueue(max_size=32)
        
        self.last_update = 0
    
    def has_pending(self) -> bool:
        """Check if there's a pending command."""
        return self.pending_position is not None
    
    def clear_pending(self) -> None:
        """Clear pending command."""
        self.pending_position = None
        self.pending_speed = None
        self.pending_time = None


class ServoBus:
    """
    High-performance multi-servo bus manager.
    
    Designed for animating up to 16+ servos at 30+ FPS using
    sync_write for atomic updates.
    """
    
    # Default settings
    DEFAULT_BAUD = 1000000
    DEFAULT_TIMEOUT_MS = 10
    DEFAULT_FRAME_MS = 33  # ~30 FPS
    
    def __init__(self, uart, baud: int = None, timeout_ms: int = None):
        """
        Initialize servo bus.
        
        Args:
            uart: MicroPython UART object (will be configured)
            baud: Baud rate (default 1M)
            timeout_ms: Response timeout (default 10ms)
        """
        self.uart = uart
        self.baud = baud or self.DEFAULT_BAUD
        self.timeout_ms = timeout_ms or self.DEFAULT_TIMEOUT_MS
        
        # Initialize protocol handler
        self.protocol = Protocol(uart, timeout_ms=self.timeout_ms)
        
        # Servo registry: id -> ServoState
        self._servos: dict = {}
        
        # Frame timing
        self._frame_ms = self.DEFAULT_FRAME_MS
        self._last_frame_time = 0
        
        # Stats
        self._frames_sent = 0
        self._sync_writes = 0
    
    @property
    def servo_count(self) -> int:
        """Number of registered servos."""
        return len(self._servos)
    
    @property
    def servo_ids(self) -> list:
        """List of registered servo IDs."""
        return list(self._servos.keys())
    
    @property
    def frame_rate(self) -> float:
        """Get configured frame rate in Hz."""
        return 1000 / self._frame_ms if self._frame_ms > 0 else 0
    
    @frame_rate.setter
    def frame_rate(self, hz: float) -> None:
        """Set frame rate in Hz."""
        if hz > 0:
            self._frame_ms = int(1000 / hz)
        else:
            self._frame_ms = 0
    
    def add_servo(self, servo_id: int, servo_type: type = None) -> 'ServoState':
        """
        Register a servo on the bus.
        
        Args:
            servo_id: Servo ID (1-253)
            servo_type: ServoType class (auto-detected if None)
        
        Returns:
            ServoState object for the servo
        """
        if servo_type is None:
            # Auto-detect servo type
            try:
                servo_type = detect_servo_type(self.protocol, servo_id)
            except:
                servo_type = STSType  # Default
        
        state = ServoState(servo_id, servo_type)
        self._servos[servo_id] = state
        return state
    
    def remove_servo(self, servo_id: int) -> None:
        """Unregister a servo."""
        if servo_id in self._servos:
            del self._servos[servo_id]
    
    def get_servo(self, servo_id: int) -> 'ServoState':
        """Get servo state by ID."""
        return self._servos.get(servo_id)
    
    def scan(self, start_id: int = 1, end_id: int = 20,
             auto_add: bool = True) -> list:
        """
        Scan bus for connected servos.
        
        Args:
            start_id: First ID to scan
            end_id: Last ID to scan
            auto_add: Automatically register found servos
        
        Returns:
            List of found servo IDs
        """
        found = []
        
        for servo_id in range(start_id, end_id + 1):
            if self.protocol.ping(servo_id):
                found.append(servo_id)
                if auto_add and servo_id not in self._servos:
                    self.add_servo(servo_id)
        
        return found
    
    # ============================================================
    # COMMAND QUEUING API
    # These methods queue commands without sending them immediately.
    # Call execute() to send all pending commands at once.
    # ============================================================
    
    def set_position(self, servo_id: int, position: int,
                     speed: int = None, time_ms: int = None) -> bool:
        """
        Queue a position command for a servo.
        
        Args:
            servo_id: Target servo ID
            position: Target position (ticks)
            speed: Optional speed (ticks/sec)
            time_ms: Optional move time (milliseconds)
        
        Returns:
            True if queued, False if servo not registered
        """
        state = self._servos.get(servo_id)
        if state is None:
            return False
        
        # Validate position for servo type
        is_signed = state.servo_type.has_multi_turn
        position = state.servo_type.validate_position(position, signed=is_signed)
        
        state.pending_position = position
        state.pending_speed = speed
        state.pending_time = time_ms
        return True
    
    def set_position_degrees(self, servo_id: int, degrees: float,
                             speed: int = None, time_ms: int = None) -> bool:
        """
        Queue a position command in degrees.
        
        Args:
            servo_id: Target servo ID
            degrees: Target angle in degrees
            speed: Optional speed
            time_ms: Optional move time
        
        Returns:
            True if queued, False if servo not registered
        """
        state = self._servos.get(servo_id)
        if state is None:
            return False
        
        position = state.servo_type.degrees_to_ticks(degrees)
        return self.set_position(servo_id, position, speed, time_ms)
    
    def set_all_positions(self, positions: dict,
                          speed: int = None, time_ms: int = None) -> int:
        """
        Queue position commands for multiple servos.
        
        Args:
            positions: Dict of {servo_id: position}
            speed: Optional speed for all servos
            time_ms: Optional move time for all servos
        
        Returns:
            Number of commands queued
        """
        count = 0
        for servo_id, position in positions.items():
            if self.set_position(servo_id, position, speed, time_ms):
                count += 1
        return count
    
    def queue_move(self, servo_id: int, position: int,
                   duration_ms: int, jerk: float = 1.0) -> bool:
        """
        Queue an S-curve animated move.
        
        This adds a motion profile to the servo's motion queue.
        Call update() at your frame rate to execute the animation.
        
        Args:
            servo_id: Target servo ID
            position: Target position (ticks)
            duration_ms: Motion duration
            jerk: Jerk factor (0.1-10.0)
        
        Returns:
            True if queued, False if servo not registered or queue full
        """
        state = self._servos.get(servo_id)
        if state is None:
            return False
        
        # Get current position as start
        start_pos = state.current_position
        if state.motion_queue.is_moving:
            # If already moving, chain from end of current motion
            start_pos = state.motion_queue._current.end_pos
        
        profile = create_scurve_move(start_pos, position, duration_ms, jerk)
        return state.motion_queue.add(profile)
    
    def queue_move_degrees(self, servo_id: int, degrees: float,
                           duration_ms: int, jerk: float = 1.0) -> bool:
        """Queue an S-curve move in degrees."""
        state = self._servos.get(servo_id)
        if state is None:
            return False
        
        position = state.servo_type.degrees_to_ticks(degrees)
        return self.queue_move(servo_id, position, duration_ms, jerk)
    
    def queue_all_moves(self, positions: dict, duration_ms: int,
                        jerk: float = 1.0) -> int:
        """
        Queue animated moves for multiple servos.
        
        All servos will complete their moves in the same duration,
        regardless of distance traveled.
        
        Args:
            positions: Dict of {servo_id: target_position}
            duration_ms: Motion duration for all
            jerk: Jerk factor
        
        Returns:
            Number of moves queued
        """
        count = 0
        for servo_id, position in positions.items():
            if self.queue_move(servo_id, position, duration_ms, jerk):
                count += 1
        return count
    
    # ============================================================
    # EXECUTION API
    # ============================================================
    
    def execute(self) -> int:
        """
        Execute all pending position commands with sync_write.
        
        This is the key method for high-performance multi-servo control.
        All pending commands are sent in a single packet.
        
        Returns:
            Number of servos updated
        """
        # Collect pending commands grouped by servo type
        # (We need separate sync_writes for different endianness)
        by_type = {}
        
        for state in self._servos.values():
            if state.pending_position is not None:
                stype = state.servo_type
                if stype not in by_type:
                    by_type[stype] = []
                by_type[stype].append(state)
        
        count = 0
        
        for servo_type, states in by_type.items():
            servo_data = []
            
            for state in states:
                # Build position data with correct endianness
                pos_bytes = servo_type.pack_word_signed(state.pending_position)
                
                if state.pending_time is not None:
                    # Include time parameter (4 bytes total: pos + time)
                    time_bytes = servo_type.pack_word(state.pending_time)
                    data = pos_bytes + time_bytes
                elif state.pending_speed is not None:
                    # Include speed parameter (4 bytes: pos + speed)
                    # Note: For speed mode, we write to different registers
                    speed_bytes = servo_type.pack_word(state.pending_speed)
                    data = pos_bytes + speed_bytes
                else:
                    # Position only (2 bytes)
                    data = pos_bytes
                
                servo_data.append((state.id, data))
                
                # Update target and clear pending
                state.target_position = state.pending_position
                state.clear_pending()
                count += 1
            
            # Send sync_write for this servo type
            if servo_data:
                data_len = len(servo_data[0][1])
                self.protocol.sync_write(
                    servo_type.reg_goal_position,
                    data_len,
                    servo_data
                )
                self._sync_writes += 1
        
        return count
    
    def update(self) -> int:
        """
        Update motion queues and execute pending commands.
        
        Call this at your desired frame rate (e.g., in a timer callback).
        Handles animated moves and sends position updates.
        
        Returns:
            Number of servos that moved
        """
        # Update all motion queues and collect new positions
        moving_count = 0
        
        for state in self._servos.values():
            if not state.motion_queue.is_empty:
                new_pos = state.motion_queue.update()
                if new_pos is not None:
                    state.pending_position = new_pos
                    moving_count += 1
        
        # Execute any pending commands
        if moving_count > 0:
            self.execute()
            self._frames_sent += 1
        
        return moving_count
    
    def run_frame(self) -> int:
        """
        Run a single animation frame with timing control.
        
        Waits until next frame time, then calls update().
        Use in a loop for continuous animation.
        
        Returns:
            Number of servos that moved
        """
        # Wait for next frame time
        now = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_frame_time)
        
        if elapsed < self._frame_ms:
            time.sleep_ms(self._frame_ms - elapsed)
        
        self._last_frame_time = time.ticks_ms()
        return self.update()
    
    # ============================================================
    # FEEDBACK API
    # ============================================================
    
    def read_position(self, servo_id: int) -> int:
        """
        Read current position from a servo.
        
        Note: This is a synchronous read. For high frame rates,
        consider using bulk_read instead.
        """
        state = self._servos.get(servo_id)
        if state is None:
            return None
        
        stype = state.servo_type
        data = self.protocol.read(servo_id, stype.reg_present_position, 2)
        position = stype.unpack_word_signed(data)
        state.current_position = position
        state.last_update = time.ticks_ms()
        return position
    
    def read_status(self, servo_id: int) -> dict:
        """
        Read full status from a servo.
        
        Returns dict with position, speed, load, voltage, temperature.
        """
        state = self._servos.get(servo_id)
        if state is None:
            return None
        
        stype = state.servo_type
        
        # Read all status registers in one read (8 bytes)
        data = self.protocol.read(servo_id, stype.reg_present_position, 8)
        
        # Parse values
        position = stype.unpack_word_signed(data[0:2])
        speed = stype.unpack_word_signed(data[2:4])
        load_raw = stype.unpack_word(data[4:6])
        voltage = data[6]
        temperature = data[7]
        
        # Parse load (bit 10 = direction)
        load_dir = 1 if (load_raw & 0x400) else -1
        load_mag = load_raw & 0x3FF
        load = load_dir * load_mag
        
        # Update state
        state.current_position = position
        state.current_speed = speed
        state.current_load = load
        state.voltage = voltage
        state.temperature = temperature
        state.last_update = time.ticks_ms()
        
        return {
            'position': position,
            'speed': speed,
            'load': load,
            'voltage': voltage / 10.0,  # Convert to volts
            'temperature': temperature,
            'angle': stype.ticks_to_degrees(position),
        }
    
    def read_all_positions(self) -> dict:
        """
        Read positions from all registered servos.
        
        Returns dict of {servo_id: position}.
        """
        positions = {}
        for servo_id in self._servos:
            try:
                pos = self.read_position(servo_id)
                if pos is not None:
                    positions[servo_id] = pos
            except:
                pass
        return positions
    
    # ============================================================
    # TORQUE CONTROL
    # ============================================================
    
    def set_torque(self, servo_id: int, enabled: bool) -> None:
        """Enable or disable torque for a servo."""
        state = self._servos.get(servo_id)
        if state is None:
            return
        
        stype = state.servo_type
        value = 1 if enabled else 0
        self.protocol.write(servo_id, stype.reg_torque_enable, bytes([value]))
        state.enabled = enabled
    
    def set_all_torque(self, enabled: bool) -> None:
        """Enable or disable torque for all servos."""
        value = 1 if enabled else 0
        
        # Use sync_write for efficiency
        servo_data = [(state.id, bytes([value])) 
                      for state in self._servos.values()]
        
        if servo_data:
            # Use STS register address (same for both types)
            self.protocol.sync_write(SMSReg.TORQUE_ENABLE, 1, servo_data)
        
        for state in self._servos.values():
            state.enabled = enabled
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def stop_all(self) -> None:
        """
        Emergency stop: disable torque and clear motion queues.
        """
        # Clear all motion queues
        for state in self._servos.values():
            state.motion_queue.clear()
            state.clear_pending()
        
        # Disable torque
        self.set_all_torque(False)
    
    def hold_all(self) -> None:
        """
        Hold all servos at current position.
        
        Enables torque and sets goal to current position.
        """
        self.set_all_torque(True)
        
        # Read current positions and set as targets
        positions = self.read_all_positions()
        self.set_all_positions(positions)
        self.execute()
    
    def stats(self) -> dict:
        """Get bus statistics."""
        return {
            'servo_count': self.servo_count,
            'frames_sent': self._frames_sent,
            'sync_writes': self._sync_writes,
            'frame_rate': self.frame_rate,
        }


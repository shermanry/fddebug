"""
Individual Servo Controller

Provides a high-level API for controlling a single servo,
wrapping the bus operations with a convenient interface.

Usage:
    from feetech import ServoBus, Servo
    
    bus = ServoBus(uart)
    bus.scan()
    
    servo = Servo(bus, 1)
    servo.move_to(2048, duration_ms=500, jerk=1.0)
    
    # Animate at 30 FPS
    while servo.is_moving:
        bus.run_frame()
"""

from .servo_types import ServoType, STSType
from .registers import SMSReg, SCSReg, Mode
from .motion import create_scurve_move


class Servo:
    """
    High-level interface for a single servo.
    
    Provides convenient methods for position control, configuration,
    and status monitoring.
    """
    
    def __init__(self, bus, servo_id: int, servo_type: type = None):
        """
        Initialize servo controller.
        
        Args:
            bus: ServoBus instance
            servo_id: Servo ID (1-253)
            servo_type: Optional ServoType class (auto-detected if None)
        """
        self._bus = bus
        self._id = servo_id
        
        # Ensure servo is registered on bus
        state = bus.get_servo(servo_id)
        if state is None:
            state = bus.add_servo(servo_id, servo_type)
        
        self._state = state
    
    @property
    def id(self) -> int:
        """Servo ID."""
        return self._id
    
    @property
    def servo_type(self) -> type:
        """ServoType class for this servo."""
        return self._state.servo_type
    
    @property
    def position(self) -> int:
        """Current position in ticks (cached, call read_position() to update)."""
        return self._state.current_position
    
    @property
    def angle(self) -> float:
        """Current angle in degrees (cached)."""
        return self.servo_type.ticks_to_degrees(self._state.current_position)
    
    @property
    def target_position(self) -> int:
        """Target position in ticks."""
        return self._state.target_position
    
    @property
    def is_moving(self) -> bool:
        """Check if servo has active motion queue."""
        return self._state.motion_queue.is_moving or self._state.has_pending()
    
    @property
    def is_enabled(self) -> bool:
        """Check if torque is enabled."""
        return self._state.enabled
    
    @property
    def voltage(self) -> float:
        """Current voltage in volts (cached)."""
        return self._state.voltage / 10.0
    
    @property
    def temperature(self) -> int:
        """Current temperature in Celsius (cached)."""
        return self._state.temperature
    
    @property
    def load(self) -> int:
        """Current load (cached, signed: positive=CW, negative=CCW)."""
        return self._state.current_load
    
    # ============================================================
    # POSITION CONTROL
    # ============================================================
    
    def move_to(self, position: int, duration_ms: int = None,
                speed: int = None, jerk: float = 1.0) -> None:
        """
        Move to a target position.
        
        Args:
            position: Target position in ticks
            duration_ms: If set, uses S-curve animation over this duration
            speed: If set (and no duration), uses hardware speed control
            jerk: Jerk factor for S-curve moves (0.1-10.0)
        
        If neither duration_ms nor speed is set, moves as fast as possible.
        """
        if duration_ms is not None:
            # Animated move with S-curve
            self._bus.queue_move(self._id, position, duration_ms, jerk)
        else:
            # Immediate move
            self._bus.set_position(self._id, position, speed=speed)
    
    def move_to_angle(self, degrees: float, duration_ms: int = None,
                      speed: int = None, jerk: float = 1.0) -> None:
        """
        Move to a target angle in degrees.
        
        Args:
            degrees: Target angle in degrees
            duration_ms: If set, uses S-curve animation
            speed: If set, uses hardware speed control
            jerk: Jerk factor for S-curve moves
        """
        position = self.servo_type.degrees_to_ticks(degrees)
        self.move_to(position, duration_ms, speed, jerk)
    
    def move_by(self, delta: int, duration_ms: int = None,
                jerk: float = 1.0) -> None:
        """
        Move by a relative amount.
        
        Args:
            delta: Position change in ticks (positive or negative)
            duration_ms: If set, uses S-curve animation
            jerk: Jerk factor for S-curve moves
        """
        target = self._state.current_position + delta
        self.move_to(target, duration_ms, jerk=jerk)
    
    def move_by_angle(self, degrees: float, duration_ms: int = None,
                      jerk: float = 1.0) -> None:
        """Move by a relative angle in degrees."""
        delta = self.servo_type.degrees_to_ticks(degrees)
        self.move_by(int(delta), duration_ms, jerk)
    
    def stop(self) -> None:
        """
        Stop current motion and hold position.
        
        Clears motion queue and sets target to current position.
        """
        self._state.motion_queue.clear()
        self._state.clear_pending()
        
        # Read current position and hold there
        pos = self.read_position()
        self._bus.set_position(self._id, pos)
        self._bus.execute()
    
    # ============================================================
    # TORQUE CONTROL
    # ============================================================
    
    def enable(self) -> None:
        """Enable torque (servo will hold position)."""
        self._bus.set_torque(self._id, True)
    
    def disable(self) -> None:
        """Disable torque (servo will be free-moving)."""
        self._bus.set_torque(self._id, False)
    
    # ============================================================
    # FEEDBACK
    # ============================================================
    
    def read_position(self) -> int:
        """Read current position from servo."""
        return self._bus.read_position(self._id)
    
    def read_status(self) -> dict:
        """
        Read full status from servo.
        
        Returns dict with position, speed, load, voltage, temperature, angle.
        """
        return self._bus.read_status(self._id)
    
    def read_angle(self) -> float:
        """Read current angle in degrees."""
        pos = self.read_position()
        return self.servo_type.ticks_to_degrees(pos)
    
    # ============================================================
    # CONFIGURATION
    # ============================================================
    
    def set_pid(self, p: int = None, i: int = None, d: int = None) -> None:
        """
        Set position PID parameters.
        
        Args:
            p: Proportional gain (0-254)
            i: Integral gain (0-254)
            d: Derivative gain (0-254)
        """
        stype = self.servo_type
        protocol = self._bus.protocol
        
        if p is not None:
            protocol.write(self._id, stype.reg_p, bytes([p]))
        if i is not None:
            protocol.write(self._id, stype.reg_i, bytes([i]))
        if d is not None:
            protocol.write(self._id, stype.reg_d, bytes([d]))
    
    def set_speed_pid(self, p: int = None, i: int = None, d: int = None) -> None:
        """
        Set speed loop PID parameters (STS/SMS only).
        
        Args:
            p: Proportional gain
            i: Integral gain
            d: Derivative gain
        """
        if not self.servo_type.has_speed_pid:
            raise NotImplementedError("Speed PID not available for this servo type")
        
        stype = self.servo_type
        protocol = self._bus.protocol
        
        if p is not None:
            protocol.write(self._id, stype.reg_speed_p, bytes([p]))
        if i is not None:
            protocol.write(self._id, stype.reg_speed_i, bytes([i]))
        if d is not None:
            protocol.write(self._id, stype.reg_speed_d, bytes([d]))
    
    def set_punch(self, value: int) -> None:
        """
        Set minimum PWM punch (starting force).
        
        Args:
            value: Punch value (0-1000)
        """
        value = max(0, min(1000, value))
        data = self.servo_type.pack_word(value)
        self._bus.protocol.write(self._id, self.servo_type.reg_punch, data)
    
    def set_max_torque(self, value: int) -> None:
        """
        Set maximum torque limit.
        
        Args:
            value: Max torque (0-1000)
        """
        value = max(0, min(1000, value))
        data = self.servo_type.pack_word(value)
        self._bus.protocol.write(self._id, self.servo_type.reg_max_torque, data)
    
    def set_angle_limits(self, min_angle: float = None, 
                         max_angle: float = None) -> None:
        """
        Set angular position limits.
        
        Args:
            min_angle: Minimum angle in degrees
            max_angle: Maximum angle in degrees
        """
        stype = self.servo_type
        protocol = self._bus.protocol
        
        if min_angle is not None:
            pos = stype.degrees_to_ticks(min_angle)
            data = stype.pack_word(pos)
            protocol.write(self._id, stype.reg_min_angle, data)
        
        if max_angle is not None:
            pos = stype.degrees_to_ticks(max_angle)
            data = stype.pack_word(pos)
            protocol.write(self._id, stype.reg_max_angle, data)
    
    def set_mode(self, mode: int) -> None:
        """
        Set operating mode (STS/SMS only).
        
        Args:
            mode: Mode constant from registers.Mode
                  0 = Position servo mode (0-4095)
                  1 = Wheel mode (speed closed-loop)
                  2 = PWM mode (speed open-loop)
                  3 = Step mode (incremental multi-turn)
        """
        if not self.servo_type.has_mode:
            raise NotImplementedError("Mode switching not available for this servo type")
        
        self._bus.protocol.write(self._id, self.servo_type.reg_mode, bytes([mode]))
    
    # ============================================================
    # STEP MODE (Mode 3 - Incremental Multi-turn)
    # ============================================================
    
    def enable_step_mode(self, speed: int = 300, acc: int = 50) -> None:
        """
        Enable step mode (Mode 3) for incremental position control.
        
        In step mode, the goal position is INCREMENTAL (delta), not absolute.
        Each write moves the servo by that many steps.
        Uses sign-magnitude encoding: positive = one direction, negative = opposite.
        
        Per Feetech docs: limits must be 0,0 for step mode.
        
        Args:
            speed: Movement speed (applied to all steps)
            acc: Acceleration value
        """
        if not self.servo_type.has_mode:
            raise NotImplementedError("Step mode not available for this servo type")
        
        import time
        stype = self.servo_type
        protocol = self._bus.protocol
        
        # Disable torque for mode change
        protocol.write(self._id, stype.reg_torque_enable, bytes([0]))
        time.sleep_ms(50)
        
        # Unlock EPROM
        self.unlock_eprom()
        time.sleep_ms(10)
        
        # Set mode 3 (step)
        protocol.write(self._id, stype.reg_mode, bytes([3]))
        
        # Set limits to 0,0 (required for step mode)
        protocol.write(self._id, stype.reg_min_angle, stype.pack_word(0))
        protocol.write(self._id, stype.reg_max_angle, stype.pack_word(0))
        
        # Lock EPROM
        self.lock_eprom()
        time.sleep_ms(50)
        
        # Set speed (before enabling torque)
        protocol.write(self._id, stype.reg_goal_speed, stype.pack_word(speed))
        
        # Set acceleration
        if stype.has_acceleration:
            protocol.write(self._id, stype.reg_acceleration, bytes([acc]))
        
        # Enable torque
        protocol.write(self._id, stype.reg_torque_enable, bytes([1]))
        time.sleep_ms(100)
    
    def disable_step_mode(self, min_limit: int = 0, max_limit: int = 4095) -> None:
        """
        Disable step mode and return to normal position mode (Mode 0).
        
        Args:
            min_limit: Minimum angle limit (default 0)
            max_limit: Maximum angle limit (default 4095)
        """
        if not self.servo_type.has_mode:
            return
        
        import time
        stype = self.servo_type
        protocol = self._bus.protocol
        
        # Disable torque
        protocol.write(self._id, stype.reg_torque_enable, bytes([0]))
        time.sleep_ms(50)
        
        self.unlock_eprom()
        time.sleep_ms(10)
        
        # Set mode 0 (position)
        protocol.write(self._id, stype.reg_mode, bytes([0]))
        
        # Restore limits
        protocol.write(self._id, stype.reg_min_angle, stype.pack_word(min_limit))
        protocol.write(self._id, stype.reg_max_angle, stype.pack_word(max_limit))
        
        self.lock_eprom()
        time.sleep_ms(50)
        
        # Enable torque
        protocol.write(self._id, stype.reg_torque_enable, bytes([1]))
    
    def step(self, steps: int) -> None:
        """
        Move by a number of steps (step mode only).
        
        Args:
            steps: Number of steps to move (positive or negative)
                   Uses sign-magnitude encoding (bit 15 = direction)
        
        Example:
            servo.enable_step_mode(speed=300)
            servo.step(500)   # Move 500 steps forward
            servo.step(500)   # Move 500 more steps forward
            servo.step(-1000) # Move 1000 steps backward
        """
        # Encode using sign-magnitude
        data = self.servo_type.pack_word_signed(steps)
        self._bus.protocol.write(self._id, self.servo_type.reg_goal_position, data)
    
    def set_step_speed(self, speed: int) -> None:
        """
        Set movement speed for step mode.
        
        Args:
            speed: Speed value (typically 50-1000)
        """
        data = self.servo_type.pack_word(speed)
        self._bus.protocol.write(self._id, self.servo_type.reg_goal_speed, data)
    
    def set_acceleration(self, value: int) -> None:
        """
        Set hardware acceleration (STS/SMS only).
        
        This controls how quickly the servo accelerates/decelerates
        when using hardware speed control.
        
        Args:
            value: Acceleration (0-254, 0=instant)
        """
        if not self.servo_type.has_acceleration:
            raise NotImplementedError("Acceleration not available for this servo type")
        
        value = max(0, min(254, value))
        self._bus.protocol.write(self._id, self.servo_type.reg_acceleration, 
                                  bytes([value]))
    
    # ============================================================
    # EPROM CONFIGURATION (Persistent)
    # ============================================================
    
    def unlock_eprom(self) -> None:
        """Unlock EPROM for writing persistent settings."""
        self._bus.protocol.write(self._id, self.servo_type.reg_lock, bytes([0]))
    
    def lock_eprom(self) -> None:
        """Lock EPROM to protect persistent settings."""
        self._bus.protocol.write(self._id, self.servo_type.reg_lock, bytes([1]))
    
    def set_id(self, new_id: int) -> None:
        """
        Change servo ID (persistent).
        
        IMPORTANT: Unlocks EPROM, changes ID, and locks EPROM.
        The servo will respond to the new ID immediately.
        
        Args:
            new_id: New servo ID (1-253)
        """
        if not 1 <= new_id <= 253:
            raise ValueError("ID must be 1-253")
        
        import time
        
        self.unlock_eprom()
        time.sleep_ms(10)
        
        self._bus.protocol.write(self._id, self.servo_type.reg_id, bytes([new_id]))
        time.sleep_ms(10)
        
        # Update internal state
        old_id = self._id
        self._id = new_id
        
        # Re-register with bus under new ID
        if old_id in self._bus._servos:
            del self._bus._servos[old_id]
        self._bus._servos[new_id] = self._state
        self._state.id = new_id
        
        self.lock_eprom()
        time.sleep_ms(10)
    
    def set_baud_rate(self, baud: int) -> None:
        """
        Change servo baud rate (persistent).
        
        IMPORTANT: After changing, you must reconfigure your UART
        to match the new baud rate.
        
        Args:
            baud: Baud rate (1000000, 500000, 250000, 128000, 
                           115200, 76800, 57600, 38400)
        """
        from .registers import BAUD_TO_CODE
        
        if baud not in BAUD_TO_CODE:
            raise ValueError(f"Invalid baud rate: {baud}")
        
        code = BAUD_TO_CODE[baud]
        
        import time
        
        self.unlock_eprom()
        time.sleep_ms(10)
        
        self._bus.protocol.write(self._id, SMSReg.BAUD_RATE, bytes([code]))
        time.sleep_ms(10)
        
        self.lock_eprom()
        time.sleep_ms(10)
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def calibrate_offset(self) -> None:
        """
        Set current position as zero point (STS/SMS only).
        
        Writes current position as offset so current position
        becomes position 0.
        """
        if not self.servo_type.has_offset:
            raise NotImplementedError("Offset not available for this servo type")
        
        import time
        
        # Read current position
        pos = self.read_position()
        
        # Write as offset (negative to make current = 0)
        offset = -pos
        data = self.servo_type.pack_word_signed(offset)
        
        self.unlock_eprom()
        time.sleep_ms(10)
        
        self._bus.protocol.write(self._id, self.servo_type.reg_offset, data)
        time.sleep_ms(10)
        
        self.lock_eprom()
        time.sleep_ms(10)
    
    def factory_reset(self) -> None:
        """
        Reset servo to factory defaults.
        
        WARNING: This resets ID to 1 and all other settings.
        """
        from .protocol import INST_RESET, build_packet
        
        packet = build_packet(self._id, INST_RESET)
        self._bus.protocol.send(packet)
    
    def __repr__(self) -> str:
        return f"Servo(id={self._id}, type={self.servo_type.name})"


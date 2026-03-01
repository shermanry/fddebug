import os
import re

def refactor():
    filepath = 'feetech_servo.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    replacements = [
        (
            '''    def read_position(self, servo_id: int) -> int:
        """Read current position.
        
        Per official SDK:
        - SCS: Returns unsigned value (0-1023)
        - STS/SMS: Decodes sign-magnitude (bit 15 = sign)
        
        For STS multi-turn mode, this can return negative values.
        """
        pos = self.read_word(servo_id, REG_PRESENT_POSITION)
        if pos >= 0 and self.end == 0:  # STS/SMS (little-endian)
            return self._from_sign_magnitude(pos, 15)
        return pos  # SCS or error''',
            '''    def read_position(self, servo_id: int) -> int:
        """Read current position."""
        return self.read_register(servo_id, REG_PRESENT_POSITION)'''
        ),
        (
            '''    def read_position_signed(self, servo_id: int) -> int:
        """Read current position as signed value (for STS/SMS multi-turn mode)
        
        Per official SDK:
        - STS/SMS: Uses sign-magnitude decoding (bit 15 = sign)
        - SCS: Always unsigned (no multi-turn support)
        """
        pos = self.read_word(servo_id, REG_PRESENT_POSITION)
        if pos >= 0:
            # Only decode sign-magnitude for STS/SMS (little-endian)
            if self.end == 0:
                return self._from_sign_magnitude(pos, 15)
            # SCS is always unsigned
            return pos
        return pos''',
            '''    def read_position_signed(self, servo_id: int) -> int:
        """Read current position (auto-applies sign-magnitude via register map if applicable)."""
        return self.read_register(servo_id, REG_PRESENT_POSITION)'''
        ),
        (
            '''    def read_word_signed(self, servo_id: int, address: int) -> int:
        """Read 16-bit signed value from servo memory
        
        Uses sign-magnitude decoding per official Feetech SDK:
        Bit 15 = sign, Bits 0-14 = magnitude
        """
        val = self.read_word(servo_id, address)
        if val >= 0:
            return self._from_sign_magnitude(val, 15)
        return val''',
            '''    def read_word_signed(self, servo_id: int, address: int) -> int:
        """Read value with automatic decoding from servo map."""
        return self.read_register(servo_id, address)'''
        ),
        (
            '''    def read_speed(self, servo_id: int) -> int:
        """Read current speed (signed - negative means reverse direction)
        
        Uses sign-magnitude with bit 15 per official Feetech SDK.
        """
        speed = self.read_word(servo_id, REG_PRESENT_SPEED)
        if speed >= 0:
            return self._from_sign_magnitude(speed, 15)
        return speed''',
            '''    def read_speed(self, servo_id: int) -> int:
        """Read current speed."""
        return self.read_register(servo_id, REG_PRESENT_SPEED)'''
        ),
        (
            '''    def read_load(self, servo_id: int) -> int:
        """Read current load (bit 10 = direction, bits 0-9 = magnitude 0-1023)
        
        Per official SDK: bit 10 indicates direction, not a sign-magnitude value.
        Returns raw value; caller should mask appropriately.
        """
        return self.read_word(servo_id, REG_PRESENT_LOAD)''',
            '''    def read_load(self, servo_id: int) -> int:
        """Read current load (bit 10 = direction, bits 0-9 = magnitude 0-1023)."""
        return self.read_register(servo_id, REG_PRESENT_LOAD)'''
        ),
        (
            '''    def read_voltage(self, servo_id: int) -> float:
        """Read current voltage in volts"""
        v = self.read_byte(servo_id, REG_PRESENT_VOLTAGE)
        if v >= 0:
            return v / 10.0
        return -1''',
            '''    def read_voltage(self, servo_id: int) -> float:
        """Read current voltage in volts"""
        v = self.read_register(servo_id, REG_PRESENT_VOLTAGE)
        if v >= 0:
            return v / 10.0
        return -1'''
        ),
        (
            '''    def read_temperature(self, servo_id: int) -> int:
        """Read current temperature in Celsius"""
        return self.read_byte(servo_id, REG_PRESENT_TEMPERATURE)''',
            '''    def read_temperature(self, servo_id: int) -> int:
        """Read current temperature in Celsius"""
        return self.read_register(servo_id, REG_PRESENT_TEMPERATURE)'''
        ),
        (
            '''    def is_moving(self, servo_id: int) -> bool:
        """Check if servo is currently moving"""
        return self.read_byte(servo_id, REG_MOVING) == 1''',
            '''    def is_moving(self, servo_id: int) -> bool:
        """Check if servo is currently moving"""
        return self.read_register(servo_id, REG_MOVING) == 1'''
        ),
        (
            '''    def read_current(self, servo_id: int) -> int:
        """Read current in mA"""
        val = self.read_word(servo_id, REG_PRESENT_CURRENT)
        if val >= 0:
            return val * 6.5  # Convert to mA
        return -1''',
            '''    def read_current(self, servo_id: int) -> int:
        """Read current in mA"""
        val = self.read_register(servo_id, REG_PRESENT_CURRENT)
        if val >= 0:
            return val * 6.5  # Convert to mA
        return -1'''
        ),
        (
            '''    def set_angle_limits(self, servo_id: int, min_angle: int, max_angle: int, servo_type: str = None) -> bool:
        """Set servo angle limits
        
        For STS/SMS servos, limits can be signed (for multi-turn mode).
        For SCS servos, limits are always unsigned (0 to max_position).
        """
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        type_class = self.get_type_class(servo_type)
        if type_class.supports_multi_turn:
            # STS/SMS: Use sign-magnitude encoding for signed limits
            self.write_word_signed(servo_id, REG_MIN_ANGLE, min_angle)
            self.write_word_signed(servo_id, REG_MAX_ANGLE, max_angle)
        else:
            # SCS: Unsigned limits only
            self.write_word(servo_id, REG_MIN_ANGLE, max(0, min_angle))
            self.write_word(servo_id, REG_MAX_ANGLE, max(0, max_angle))
        
        return self.lock_eprom(servo_id, servo_type)''',
            '''    def set_angle_limits(self, servo_id: int, min_angle: int, max_angle: int, servo_type: str = None) -> bool:
        """Set servo angle limits"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        # write_register uses the memory map to automatically figure out sizes and sign encoding
        self.write_register(servo_id, REG_MIN_ANGLE, min_angle)
        self.write_register(servo_id, REG_MAX_ANGLE, max_angle)
        
        return self.lock_eprom(servo_id, servo_type)'''
        ),
        (
            '''    def set_offset(self, servo_id: int, offset: int) -> bool:
        """
        Set position offset (STS/SMS only)
        
        Args:
            offset: Signed offset value (-32767 to +32767)
        
        Uses sign-magnitude encoding per official Feetech SDK.
        """
        type_class = self.get_type_class('sts')
        if not type_class.supports_offset:
            return False
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
        # Use sign-magnitude encoding for offset
        result = self.write_word_signed(servo_id, type_class.offset_register, offset)
        self.lock_eprom(servo_id, 'sts')
        return result''',
            '''    def set_offset(self, servo_id: int, offset: int) -> bool:
        """Set position offset (STS/SMS only)"""
        type_class = self.get_type_class('sts')
        if not type_class.supports_offset:
            return False
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
            
        result = self.write_register(servo_id, type_class.offset_register, offset)
        self.lock_eprom(servo_id, 'sts')
        return result'''
        ),
        (
            '''    def write_pwm(self, servo_id: int, pwm: int) -> bool:
        """
        Write PWM output (-1000 to 1000)
        
        Requires PWM mode to be enabled first.
        
        Note: Uses sign-magnitude with bit 10 per official SDK
        """
        pwm = self._to_sign_magnitude(pwm, 10)
        
        low, high = self._host2scs(pwm & 0xFFFF)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_TIME, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)''',
            '''    def write_pwm(self, servo_id: int, pwm: int) -> bool:
        """Write PWM output"""
        return self.write_register(servo_id, REG_GOAL_TIME, pwm)'''
        ),
        (
            '''    def write_position(self, servo_id: int, position: int, time_ms: int = 0, speed: int = 0) -> bool:
        """
        Move servo to position
        
        Args:
            servo_id: Servo ID
            position: Target position (can be signed for STS/SMS multi-turn mode)
            time_ms: Movement time in milliseconds (0 = use speed)
            speed: Maximum speed in steps/second (0 = maximum)
        
        Returns:
            True if command sent successfully
        
        Note: Per official SDK:
        - SCS servos: position is unsigned (no sign-magnitude)
        - STS/SMS servos: position uses sign-magnitude with bit 15
        """
        # Handle signed position for STS/SMS only (per official SDK)
        # SCS servos don't support negative positions
        if self.end == 0:  # Little-endian = STS/SMS
            position = self._to_sign_magnitude(position, 15)
        else:  # Big-endian = SCS (unsigned only)
            position = max(0, position) & 0xFFFF
        
        pos_l, pos_h = self._host2scs(position & 0xFFFF)
        time_l, time_h = self._host2scs(time_ms)
        speed_l, speed_h = self._host2scs(speed)
        
        data = bytes([pos_l, pos_h, time_l, time_h, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_POSITION, data, Instruction.WRITE)
        return self._ack(servo_id)''',
            '''    def write_position(self, servo_id: int, position: int, time_ms: int = 0, speed: int = 0) -> bool:
        """Move servo to position"""
        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        
        reg_info = memory_map.get(REG_GOAL_POSITION)
        if reg_info and reg_info['signed_bit'] is not None:
            position = self._to_sign_magnitude(position, reg_info['signed_bit'])
        else:
            position = max(0, position) & 0xFFFF
            
        pos_l, pos_h = self._host2scs(position & 0xFFFF)
        time_l, time_h = self._host2scs(time_ms)
        speed_l, speed_h = self._host2scs(speed)
        
        data = bytes([pos_l, pos_h, time_l, time_h, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_POSITION, data, Instruction.WRITE)
        return self._ack(servo_id)'''
        ),
        (
            '''        for servo_id, position, time_ms, speed in servos:
            # Apply sign-magnitude encoding for STS/SMS (little-endian)
            if self.end == 0:  # Little-endian = STS/SMS
                position = self._to_sign_magnitude(position, 15)
            else:  # Big-endian = SCS (unsigned only)
                position = max(0, position) & 0xFFFF''',
            '''        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        reg_info = memory_map.get(REG_GOAL_POSITION)

        for servo_id, position, time_ms, speed in servos:
            if reg_info and reg_info['signed_bit'] is not None:
                position = self._to_sign_magnitude(position, reg_info['signed_bit'])
            else:
                position = max(0, position) & 0xFFFF'''
        )
    ]

    for old, new in replacements:
        if old not in content:
            print(f"Warning: Could not find block:\n{old[:50]}...")
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Refactored methods in feetech_servo.py")

if __name__ == '__main__':
    refactor()

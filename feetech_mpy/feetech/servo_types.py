"""
Servo Type Definitions

Handles the differences between SCS and STS/SMS servo series:
- Endianness (SCS=big, STS/SMS=little)
- Resolution (SCS=1024, STS=4096)
- Angle range (SCS=300°, STS=360°)
- Feature availability (mode, offset, multi-turn)

This abstraction allows the rest of the library to work uniformly
with any servo type.
"""

from .registers import SCSReg, SMSReg, Mode


class ServoType:
    """
    Base class defining servo characteristics.
    
    Subclass this for each servo series to define its specific
    properties and behaviors.
    """
    
    # Identity
    name: str = "Unknown"
    series: str = "unknown"
    
    # Byte order for 16-bit values
    # 'big' = MSB first, 'little' = LSB first
    endian: str = "little"
    
    # Position resolution (ticks per full range)
    resolution: int = 4096
    
    # Angular range in degrees
    angle_range: float = 360.0
    
    # Feature flags
    has_mode: bool = True          # Operating mode register
    has_offset: bool = True        # Position offset calibration
    has_multi_turn: bool = True    # Multi-turn position mode
    has_speed_pid: bool = True     # Speed loop PID tuning
    has_acceleration: bool = True  # Hardware acceleration control
    
    # Register addresses (override in subclass)
    reg_id: int = SMSReg.ID
    reg_lock: int = SMSReg.LOCK
    reg_goal_position: int = SMSReg.GOAL_POSITION_L
    reg_goal_speed: int = SMSReg.GOAL_SPEED_L
    reg_goal_time: int = SMSReg.GOAL_TIME_L
    reg_present_position: int = SMSReg.PRESENT_POSITION_L
    reg_present_speed: int = SMSReg.PRESENT_SPEED_L
    reg_present_load: int = SMSReg.PRESENT_LOAD_L
    reg_present_voltage: int = SMSReg.PRESENT_VOLTAGE
    reg_present_temp: int = SMSReg.PRESENT_TEMPERATURE
    reg_torque_enable: int = SMSReg.TORQUE_ENABLE
    reg_moving: int = SMSReg.MOVING
    reg_min_angle: int = SMSReg.MIN_ANGLE_LIMIT_L
    reg_max_angle: int = SMSReg.MAX_ANGLE_LIMIT_L
    reg_mode: int = SMSReg.MODE
    reg_offset: int = SMSReg.OFS_L
    reg_acceleration: int = SMSReg.ACCELERATION
    
    # PID registers
    reg_p: int = SMSReg.P_COEF
    reg_i: int = SMSReg.I_COEF
    reg_d: int = SMSReg.D_COEF
    reg_speed_p: int = SMSReg.SPEED_P
    reg_speed_i: int = SMSReg.SPEED_I
    reg_speed_d: int = SMSReg.SPEED_D
    
    # Protection registers
    reg_punch: int = SMSReg.PUNCH_L
    reg_max_torque: int = SMSReg.MAX_TORQUE_L
    reg_max_temp: int = SMSReg.MAX_TEMP
    reg_max_voltage: int = SMSReg.MAX_VOLTAGE
    reg_min_voltage: int = SMSReg.MIN_VOLTAGE
    
    @classmethod
    def pack_word(cls, value: int) -> bytes:
        """Pack a 16-bit value with correct endianness."""
        value = value & 0xFFFF  # Ensure unsigned 16-bit
        if cls.endian == 'big':
            return bytes([value >> 8, value & 0xFF])
        else:
            return bytes([value & 0xFF, value >> 8])
    
    @classmethod
    def unpack_word(cls, data: bytes) -> int:
        """Unpack a 16-bit value with correct endianness."""
        if cls.endian == 'big':
            return (data[0] << 8) | data[1]
        else:
            return data[0] | (data[1] << 8)
    
    @classmethod
    def unpack_word_signed(cls, data: bytes) -> int:
        """Unpack a signed 16-bit value using sign-magnitude (bit 15 = sign).
        
        Per official Feetech SDK:
        - Bit 15 = sign (1 = negative)
        - Bits 0-14 = magnitude (0-32767)
        """
        value = cls.unpack_word(data)
        if value & 0x8000:  # Sign bit set
            return -(value & 0x7FFF)  # Extract magnitude and negate
        return value
    
    @classmethod
    def pack_word_signed(cls, value: int) -> bytes:
        """Pack a signed 16-bit value using sign-magnitude (bit 15 = sign).
        
        Per official Feetech SDK:
        - Negative values: bit 15 = 1, bits 0-14 = magnitude
        - Positive values: bit 15 = 0, bits 0-14 = value
        
        Example: -100 → 0x8064 (32868)
        
        Values are clamped to valid range (-32767 to +32767).
        """
        if value < 0:
            magnitude = min(-value, 0x7FFF)  # Clamp to max magnitude
            value = magnitude | 0x8000  # Set sign bit + magnitude
        else:
            value = min(value, 0x7FFF)  # Clamp positive to max magnitude
        return cls.pack_word(value)
    
    @classmethod
    def ticks_to_degrees(cls, ticks: int) -> float:
        """Convert position ticks to degrees."""
        return (ticks / cls.resolution) * cls.angle_range
    
    @classmethod
    def degrees_to_ticks(cls, degrees: float) -> int:
        """Convert degrees to position ticks."""
        return int((degrees / cls.angle_range) * cls.resolution)
    
    @classmethod
    def validate_position(cls, position: int, signed: bool = False) -> int:
        """
        Validate and clamp position to valid range.
        
        Args:
            position: Target position in ticks
            signed: If True, allow negative values (multi-turn)
        
        Returns:
            Clamped position value
        """
        if signed and cls.has_multi_turn:
            # Multi-turn range: -32768 to 32767
            return max(-32768, min(32767, position))
        else:
            # Single-turn range: 0 to resolution-1
            return max(0, min(cls.resolution - 1, position))


class SCSType(ServoType):
    """
    SCS series servos (e.g., SCS0009).
    
    Characteristics:
    - Big-endian byte order
    - 1024 tick resolution
    - 300° angle range
    - No mode switching
    - No position offset
    - No multi-turn support
    """
    
    name = "SCS"
    series = "scs"
    
    endian = "big"
    resolution = 1024
    angle_range = 300.0
    
    has_mode = False
    has_offset = False
    has_multi_turn = False
    has_speed_pid = False
    has_acceleration = False
    
    # SCS-specific register addresses
    reg_lock = SCSReg.LOCK
    reg_id = SCSReg.ID
    reg_goal_position = SCSReg.GOAL_POSITION_L
    reg_goal_speed = SCSReg.GOAL_SPEED_L
    reg_goal_time = SCSReg.GOAL_TIME_L
    reg_present_position = SCSReg.PRESENT_POSITION_L
    reg_present_speed = SCSReg.PRESENT_SPEED_L
    reg_present_load = SCSReg.PRESENT_LOAD_L
    reg_present_voltage = SCSReg.PRESENT_VOLTAGE
    reg_present_temp = SCSReg.PRESENT_TEMPERATURE
    reg_torque_enable = SCSReg.TORQUE_ENABLE
    reg_moving = SCSReg.MOVING
    reg_min_angle = SCSReg.MIN_ANGLE_LIMIT_L
    reg_max_angle = SCSReg.MAX_ANGLE_LIMIT_L
    
    reg_p = SCSReg.P_COEF
    reg_i = SCSReg.I_COEF
    reg_d = SCSReg.D_COEF
    
    reg_punch = SCSReg.PUNCH_L
    reg_max_torque = SCSReg.MAX_TORQUE_L
    reg_max_temp = SCSReg.MAX_TEMP
    reg_max_voltage = SCSReg.MAX_VOLTAGE
    reg_min_voltage = SCSReg.MIN_VOLTAGE
    
    @classmethod
    def unpack_word_signed(cls, data: bytes) -> int:
        """SCS servos don't support signed values - return unsigned."""
        return cls.unpack_word(data)
    
    @classmethod
    def pack_word_signed(cls, value: int) -> bytes:
        """SCS servos don't support signed values - clamp to unsigned."""
        value = max(0, value) & 0xFFFF
        return cls.pack_word(value)


class STSType(ServoType):
    """
    STS series servos (e.g., STS3215).
    
    Characteristics:
    - Little-endian byte order
    - 4096 tick resolution
    - 360° angle range
    - Mode switching (position, wheel, step, multi-turn)
    - Position offset calibration
    - Multi-turn support
    - Speed loop PID
    - Hardware acceleration control
    """
    
    name = "STS"
    series = "sts"
    
    endian = "little"
    resolution = 4096
    angle_range = 360.0
    
    has_mode = True
    has_offset = True
    has_multi_turn = True
    has_speed_pid = True
    has_acceleration = True


class SMSType(ServoType):
    """
    SMS series servos (similar to STS).
    
    Same characteristics as STS, just different model line.
    """
    
    name = "SMS"
    series = "sms"
    
    endian = "little"
    resolution = 4096
    angle_range = 360.0
    
    has_mode = True
    has_offset = True
    has_multi_turn = True
    has_speed_pid = True
    has_acceleration = True


# Registry of known servo types
SERVO_TYPES = {
    'scs': SCSType,
    'sts': STSType,
    'sms': SMSType,
}


def detect_servo_type(protocol, servo_id: int) -> type:
    """
    Auto-detect servo type by probing register values.
    
    Detection strategy:
    1. Read MAX_ANGLE_LIMIT as little-endian
    2. If value > 4096, it's likely big-endian (SCS)
    3. Verify by re-reading with big-endian interpretation
    
    Args:
        protocol: Protocol instance for communication
        servo_id: Servo ID to probe
    
    Returns:
        ServoType subclass (SCSType, STSType, etc.)
    """
    try:
        # Read max angle limit (2 bytes)
        data = protocol.read(servo_id, SMSReg.MAX_ANGLE_LIMIT_L, 2)
        
        # Try little-endian first (STS/SMS)
        value_le = data[0] | (data[1] << 8)
        
        if value_le > 4096:
            # Impossibly high for little-endian, must be big-endian (SCS)
            # Verify: big-endian interpretation should be <= 1023
            value_be = (data[0] << 8) | data[1]
            if value_be <= 1023:
                return SCSType
        
        # Check resolution by looking at the actual max limit
        if value_le <= 1023:
            # Could be SCS or STS with low limit
            # Try reading model version to distinguish
            try:
                model_data = protocol.read(servo_id, SMSReg.MODEL_L, 2)
                model = model_data[0] | (model_data[1] << 8)
                if model > 0 and model < 1000:
                    # Valid model number suggests STS/SMS
                    return STSType
            except:
                pass
            
            # Default to SCS for low resolution
            return SCSType
        
        # Default to STS for high resolution values
        return STSType
        
    except Exception:
        # If detection fails, default to STS (more common, safer)
        return STSType


def get_servo_type(name: str) -> type:
    """
    Get servo type class by name.
    
    Args:
        name: Servo type name ('scs', 'sts', 'sms')
    
    Returns:
        ServoType subclass
    
    Raises:
        ValueError: If type name is unknown
    """
    name = name.lower()
    if name not in SERVO_TYPES:
        raise ValueError(f"Unknown servo type: {name}")
    return SERVO_TYPES[name]


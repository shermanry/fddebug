"""
Feetech Servo Register Definitions

Complete register maps for SCS and STS/SMS servo series.
Registers are divided into EPROM (persistent) and RAM (volatile) sections.

IMPORTANT: EPROM writes require unlock/lock sequence and persist across power cycles.
RAM writes take effect immediately but are lost on power cycle.
"""

from micropython import const


class SCSReg:
    """
    Register addresses for SCS series servos (e.g., SCS0009).
    
    Note: SCS uses BIG-ENDIAN byte order for 16-bit values.
    """
    
    # ===== EPROM Area (persistent) =====
    
    # Firmware version (read-only)
    VERSION_L = const(0x00)
    VERSION_H = const(0x01)
    
    # Servo ID (1-253, 254=broadcast)
    ID = const(0x05)
    
    # Baud rate setting
    # 0=1M, 1=500K, 2=250K, 3=128K, 4=115200, 5=76800, 6=57600, 7=38400
    BAUD_RATE = const(0x06)
    
    # Response delay (0-254, units of 2us)
    RETURN_DELAY = const(0x07)
    
    # Response level (0=no response, 1=respond to READ only, 2=respond to all)
    RESPONSE_STATUS_LEVEL = const(0x08)
    
    # Angle limits (position range)
    MIN_ANGLE_LIMIT_L = const(0x09)
    MIN_ANGLE_LIMIT_H = const(0x0A)
    MAX_ANGLE_LIMIT_L = const(0x0B)
    MAX_ANGLE_LIMIT_H = const(0x0C)
    
    # Temperature limit (Celsius, 0-100)
    MAX_TEMP = const(0x0D)
    
    # Voltage limits (units of 0.1V)
    MAX_VOLTAGE = const(0x0E)
    MIN_VOLTAGE = const(0x0F)
    
    # Maximum torque (0-1000)
    MAX_TORQUE_L = const(0x10)
    MAX_TORQUE_H = const(0x11)
    
    # Reserved settings
    SETTING_BYTE = const(0x12)
    UNLOADING_CONDITION = const(0x13)
    
    # LED alarm conditions (bitmask)
    LED_ALARM_CONDITION = const(0x14)
    
    # PID parameters
    P_COEF = const(0x15)
    D_COEF = const(0x16)
    I_COEF = const(0x17)
    
    # Minimum starting force (0-1000)
    PUNCH_L = const(0x18)
    PUNCH_H = const(0x19)
    
    # CW/CCW dead zone
    CW_DEAD = const(0x1A)
    CCW_DEAD = const(0x1B)
    
    # Protection current (units vary by model)
    PROTECTION_CURRENT_L = const(0x1C)
    PROTECTION_CURRENT_H = const(0x1D)
    
    # Angular resolution
    ANGULAR_RESOLUTION = const(0x1E)
    
    # Position offset (not available on SCS)
    # OFS_L = const(0x1F)
    # OFS_H = const(0x20)
    
    # Mode control (not available on SCS)
    # MODE = const(0x21)
    
    # Protection time
    PROTECTION_TIME = const(0x22)
    
    # Overload torque
    OVERLOAD_TORQUE = const(0x23)
    
    # Speed loop PID (some models)
    SPEED_P = const(0x24)
    SPEED_I = const(0x25)
    SPEED_D = const(0x26)
    
    # EPROM lock register
    LOCK = const(0x30)  # Address 48
    
    # ===== RAM Area (volatile) =====
    
    # Torque enable (0=off, 1=on)
    TORQUE_ENABLE = const(0x28)
    
    # Goal position
    GOAL_POSITION_L = const(0x2A)
    GOAL_POSITION_H = const(0x2B)
    
    # Goal time (for time-based moves)
    GOAL_TIME_L = const(0x2C)
    GOAL_TIME_H = const(0x2D)
    
    # Goal speed
    GOAL_SPEED_L = const(0x2E)
    GOAL_SPEED_H = const(0x2F)
    
    # Lock RAM (write protection)
    LOCK_RAM = const(0x37)
    
    # ===== Read-only status registers =====
    
    # Current position
    PRESENT_POSITION_L = const(0x38)
    PRESENT_POSITION_H = const(0x39)
    
    # Current speed
    PRESENT_SPEED_L = const(0x3A)
    PRESENT_SPEED_H = const(0x3B)
    
    # Current load (torque)
    # Bit 10 = direction, Bits 0-9 = magnitude
    PRESENT_LOAD_L = const(0x3C)
    PRESENT_LOAD_H = const(0x3D)
    
    # Current voltage (units of 0.1V)
    PRESENT_VOLTAGE = const(0x3E)
    
    # Current temperature (Celsius)
    PRESENT_TEMPERATURE = const(0x3F)
    
    # Async write flag
    ASYNC_WRITE_FLAG = const(0x40)
    
    # Servo status
    SERVO_STATUS = const(0x41)
    
    # Moving flag
    MOVING = const(0x42)
    
    # Current current (mA on some models)
    PRESENT_CURRENT_L = const(0x45)
    PRESENT_CURRENT_H = const(0x46)


class SMSReg:
    """
    Register addresses for SMS/STS series servos (e.g., STS3215).
    
    Note: SMS/STS uses LITTLE-ENDIAN byte order for 16-bit values.
    """
    
    # ===== EPROM Area (persistent) =====
    
    # Firmware version (read-only)
    VERSION_L = const(0x00)
    VERSION_H = const(0x01)
    
    # Model number
    MODEL_L = const(0x03)
    MODEL_H = const(0x04)
    
    # Servo ID (1-253, 254=broadcast)
    ID = const(0x05)
    
    # Baud rate setting
    BAUD_RATE = const(0x06)
    
    # Response delay
    RETURN_DELAY = const(0x07)
    
    # Response level
    RESPONSE_STATUS_LEVEL = const(0x08)
    
    # Angle limits
    MIN_ANGLE_LIMIT_L = const(0x09)
    MIN_ANGLE_LIMIT_H = const(0x0A)
    MAX_ANGLE_LIMIT_L = const(0x0B)
    MAX_ANGLE_LIMIT_H = const(0x0C)
    
    # Temperature limit
    MAX_TEMP = const(0x0D)
    
    # Voltage limits
    MAX_VOLTAGE = const(0x0E)
    MIN_VOLTAGE = const(0x0F)
    
    # Maximum torque
    MAX_TORQUE_L = const(0x10)
    MAX_TORQUE_H = const(0x11)
    
    # Settings
    SETTING_BYTE = const(0x12)
    UNLOADING_CONDITION = const(0x13)
    LED_ALARM_CONDITION = const(0x14)
    
    # Position PID
    P_COEF = const(0x15)
    D_COEF = const(0x16)
    I_COEF = const(0x17)
    
    # Punch (minimum PWM)
    PUNCH_L = const(0x18)
    PUNCH_H = const(0x19)
    
    # Dead zones
    CW_DEAD = const(0x1A)
    CCW_DEAD = const(0x1B)
    
    # Protection settings
    PROTECTION_CURRENT_L = const(0x1C)
    PROTECTION_CURRENT_H = const(0x1D)
    ANGULAR_RESOLUTION = const(0x1E)
    
    # Position offset (SIGNED, for calibration)
    OFS_L = const(0x1F)
    OFS_H = const(0x20)
    
    # Operating mode (per Feetech documentation)
    # 0 = Position servo mode (0-4095)
    # 1 = Wheel mode (speed closed-loop)
    # 2 = PWM mode (speed open-loop)
    # 3 = Step mode (incremental multi-turn)
    MODE = const(0x21)
    
    # Protection time
    PROTECTION_TIME = const(0x22)
    
    # Overload torque
    OVERLOAD_TORQUE = const(0x23)
    
    # Speed loop PID (STS series)
    SPEED_P = const(0x24)
    SPEED_I = const(0x25)
    SPEED_D = const(0x26)
    
    # Torque on boot
    TORQUE_ON_BOOT = const(0x27)
    
    # Acceleration (for motion profiling)
    ACCELERATION = const(0x29)
    
    # EPROM lock register
    LOCK = const(0x37)  # Address 55
    
    # ===== RAM Area (volatile) =====
    
    # Torque enable
    TORQUE_ENABLE = const(0x28)
    
    # Goal position (SIGNED for multi-turn)
    GOAL_POSITION_L = const(0x2A)
    GOAL_POSITION_H = const(0x2B)
    
    # Goal time (for time-based moves)
    GOAL_TIME_L = const(0x2C)
    GOAL_TIME_H = const(0x2D)
    
    # Goal speed
    GOAL_SPEED_L = const(0x2E)
    GOAL_SPEED_H = const(0x2F)
    
    # Lock RAM
    LOCK_RAM = const(0x37)
    
    # ===== Read-only status registers =====
    
    # Current position (SIGNED for multi-turn)
    PRESENT_POSITION_L = const(0x38)
    PRESENT_POSITION_H = const(0x39)
    
    # Current speed (SIGNED)
    PRESENT_SPEED_L = const(0x3A)
    PRESENT_SPEED_H = const(0x3B)
    
    # Current load
    PRESENT_LOAD_L = const(0x3C)
    PRESENT_LOAD_H = const(0x3D)
    
    # Current voltage
    PRESENT_VOLTAGE = const(0x3E)
    
    # Current temperature
    PRESENT_TEMPERATURE = const(0x3F)
    
    # Async write flag
    ASYNC_WRITE_FLAG = const(0x40)
    
    # Servo status
    SERVO_STATUS = const(0x41)
    
    # Moving flag
    MOVING = const(0x42)
    
    # Current (mA)
    PRESENT_CURRENT_L = const(0x45)
    PRESENT_CURRENT_H = const(0x46)


# Baud rate lookup table
BAUD_RATES = {
    0: 1000000,
    1: 500000,
    2: 250000,
    3: 128000,
    4: 115200,
    5: 76800,
    6: 57600,
    7: 38400,
}

# Reverse lookup
BAUD_TO_CODE = {v: k for k, v in BAUD_RATES.items()}


# Operating modes (per Feetech documentation)
class Mode:
    POSITION = const(0)          # Standard position servo (0-4095)
    WHEEL = const(1)             # Wheel mode - speed closed-loop
    PWM = const(2)               # PWM mode - speed open-loop
    STEP = const(3)              # Step/Multi-turn mode (incremental position)


# LED alarm bits
class AlarmBit:
    VOLTAGE = const(0x01)
    ANGLE_LIMIT = const(0x02)
    OVERHEAT = const(0x04)
    RANGE = const(0x08)
    CHECKSUM = const(0x10)
    OVERLOAD = const(0x20)
    INSTRUCTION = const(0x40)


# Unloading condition bits  
class UnloadBit:
    VOLTAGE = const(0x01)
    ANGLE_LIMIT = const(0x02)
    OVERHEAT = const(0x04)


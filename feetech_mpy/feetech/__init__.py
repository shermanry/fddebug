"""
Feetech Servo Library for MicroPython

A high-performance, modular library for controlling Feetech SCS and STS
series servos on RP2040 and other MicroPython-compatible microcontrollers.

Features:
- Support for SCS0009, STS3215, and other Feetech servos
- Automatic endianness handling (SCS=big, STS=little)
- Async batch commands via sync_write
- S-curve motion profiles with jerk control
- Frame-rate controlled animation scheduler
- Motion queue for smooth sequencing

Quick Start:
    from machine import UART
    from feetech import ServoBus, Servo, Scheduler
    
    # Initialize UART (RP2040 example)
    uart = UART(0, baudrate=1000000, tx=Pin(0), rx=Pin(1))
    
    # Create bus and scan for servos
    bus = ServoBus(uart)
    found = bus.scan()
    print(f"Found servos: {found}")
    
    # Create servo controller
    servo = Servo(bus, 1)
    
    # Animated move with S-curve
    servo.move_to(2048, duration_ms=500, jerk=1.0)
    
    # Run animation at 30 FPS
    scheduler = Scheduler(bus, fps=30)
    scheduler.run_until_complete()

For Waveshare Bus Servo Adapter:
    # The adapter uses CH340 USB-UART
    # Connect to RP2040 via UART TX/RX pins
    # Default baud rate: 1000000

Author: Ryan Sherman
License: MIT
"""

__version__ = "1.0.0"

# Core classes
from .protocol import (
    Protocol,
    ProtocolError,
    TimeoutError,
    ChecksumError,
    StatusError,
    BROADCAST_ID,
)

from .registers import (
    SCSReg,
    SMSReg,
    Mode,
    BAUD_RATES,
    BAUD_TO_CODE,
)

from .servo_types import (
    ServoType,
    SCSType,
    STSType,
    SMSType,
    detect_servo_type,
    get_servo_type,
)

from .motion import (
    MotionProfile,
    LinearProfile,
    TrapezoidalProfile,
    SCurveProfile,
    MotionQueue,
    create_scurve_move,
    interpolate_positions,
)

from .bus import (
    ServoBus,
    ServoState,
)

from .servo import (
    Servo,
)

from .scheduler import (
    Scheduler,
    Animation,
    create_wave_animation,
)

from .blending import (
    HermiteSpline,
    BlendableProfile,
    MotionState,
    CatmullRomSpline,
    SplineAnimation,
    create_blend_profile,
)

# Viper-optimized math (optional, for advanced users)
try:
    from .viper_math import (
        FP_ONE,
        FP_SHIFT,
        smoothstep5,
        smoothstep3,
        interpolate_position,
        float_to_fp,
        fp_to_float,
    )
    VIPER_AVAILABLE = True
except ImportError:
    VIPER_AVAILABLE = False

# Convenience aliases
Bus = ServoBus

__all__ = [
    # Version
    '__version__',
    
    # Protocol
    'Protocol',
    'ProtocolError',
    'TimeoutError',
    'ChecksumError',
    'StatusError',
    'BROADCAST_ID',
    
    # Registers
    'SCSReg',
    'SMSReg',
    'Mode',
    'BAUD_RATES',
    'BAUD_TO_CODE',
    
    # Servo Types
    'ServoType',
    'SCSType',
    'STSType',
    'SMSType',
    'detect_servo_type',
    'get_servo_type',
    
    # Motion
    'MotionProfile',
    'LinearProfile',
    'TrapezoidalProfile',
    'SCurveProfile',
    'MotionQueue',
    'create_scurve_move',
    'interpolate_positions',
    
    # Bus
    'ServoBus',
    'ServoState',
    'Bus',
    
    # Servo
    'Servo',
    
    # Scheduler
    'Scheduler',
    'Animation',
    'create_wave_animation',
    
    # Blending
    'HermiteSpline',
    'BlendableProfile',
    'MotionState',
    'CatmullRomSpline',
    'SplineAnimation',
    'create_blend_profile',
    
    # Viper optimization status
    'VIPER_AVAILABLE',
]


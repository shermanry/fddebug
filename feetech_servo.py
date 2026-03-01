#!/usr/bin/env python3
"""
Feetech Servo Controller for macOS/Windows
Reverse-engineered from FD debugger SDK

Supports: SCS, SMS, STS series servos

Compatible USB Adapters:
  - Feetech URT-1 (CH340)
  - Waveshare Bus Servo Adapter v1.1 (CH340/CP210x)
  - Any CH340/CH341/CP210x/FTDI USB-to-TTL adapter
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional, List, Tuple, Dict, Type
from dataclasses import dataclass
from enum import IntEnum
from abc import ABC, abstractmethod


# ============================================================================
# Protocol Constants
# ============================================================================

class Instruction(IntEnum):
    """Servo instruction set"""
    PING = 0x01
    READ = 0x02
    WRITE = 0x03
    REG_WRITE = 0x04      # Async write (buffered)
    REG_ACTION = 0x05     # Execute buffered writes
    SYNC_WRITE = 0x83     # Write to multiple servos


class BaudRate(IntEnum):
    """Baud rate settings (for servo configuration)"""
    BAUD_1M = 0
    BAUD_500K = 1
    BAUD_250K = 2
    BAUD_128K = 3
    BAUD_115200 = 4
    BAUD_76800 = 5
    BAUD_57600 = 6
    BAUD_38400 = 7


# Memory map for SCS/SCSCL series (complete EPROM)
class SCSReg(IntEnum):
    """SCSCL series register addresses - Full EPROM map"""
    # EPROM (read-only)
    VERSION_L = 3
    VERSION_H = 4
    # EPROM (read/write) - Configuration
    ID = 5
    BAUD_RATE = 6
    RETURN_DELAY = 7          # Response delay time (2μs units)
    RESPONSE_STATUS_LEVEL = 8  # 0=no response, 1=respond to READ, 2=respond to all
    MIN_ANGLE_LIMIT_L = 9
    MIN_ANGLE_LIMIT_H = 10
    MAX_ANGLE_LIMIT_L = 11
    MAX_ANGLE_LIMIT_H = 12
    MAX_TEMP = 13             # Max temperature limit (°C)
    MAX_VOLTAGE = 14          # Max input voltage (0.1V units)
    MIN_VOLTAGE = 15          # Min input voltage (0.1V units)
    MAX_TORQUE_L = 16         # Max torque limit (0-1023)
    MAX_TORQUE_H = 17
    PHASE = 18                # Magnetic encoder phase
    UNLOADING_CONDITION = 19  # Unloading behavior setting
    LED_ALARM_CONDITION = 20  # LED alarm triggers
    P_COEFFICIENT = 21        # PID - Proportional
    D_COEFFICIENT = 22        # PID - Derivative
    I_COEFFICIENT = 23        # PID - Integral
    PUNCH_L = 24              # Minimum PWM (startup force)
    PUNCH_H = 25
    CW_DEAD = 26              # Clockwise dead band
    CCW_DEAD = 27             # Counter-clockwise dead band
    PROTECTION_CURRENT_L = 28 # Overload protection current
    PROTECTION_CURRENT_H = 29
    ANGULAR_RESOLUTION = 30   # Position resolution
    POSITION_OFFSET_L = 31    # Position offset
    POSITION_OFFSET_H = 32
    OPERATION_MODE = 33       # 0=position, 1=speed, 2=PWM
    PROTECTION_TORQUE = 34    # Overload torque threshold
    PROTECTION_TIME = 35      # Overload time threshold
    OVERLOAD_TORQUE = 36      # Startup overload torque
    SPEED_CLOSED_LOOP_P = 37  # Speed loop P coefficient
    OVERCURRENT_TIME = 38     # Overcurrent protection time
    VELOCITY_I = 39           # Speed loop I coefficient
    # SRAM (read/write)
    TORQUE_ENABLE = 40
    ACC = 41                  # Acceleration
    GOAL_POSITION_L = 42
    GOAL_POSITION_H = 43
    GOAL_TIME_L = 44
    GOAL_TIME_H = 45
    GOAL_SPEED_L = 46
    GOAL_SPEED_H = 47
    LOCK = 48                 # EPROM lock (SCS series)
    # SRAM (read-only)
    PRESENT_POSITION_L = 56
    PRESENT_POSITION_H = 57
    PRESENT_SPEED_L = 58
    PRESENT_SPEED_H = 59
    PRESENT_LOAD_L = 60
    PRESENT_LOAD_H = 61
    PRESENT_VOLTAGE = 62
    PRESENT_TEMPERATURE = 63
    ASYNC_WRITE_FLAG = 64     # REG_WRITE flag
    SERVO_STATUS = 65         # Status flags
    MOVING = 66
    PRESENT_CURRENT_L = 69
    PRESENT_CURRENT_H = 70


# Memory map for SMS/STS/SMSBL series (complete EPROM)
class SMSReg(IntEnum):
    """SMSBL/STS series register addresses - Full EPROM map"""
    # EPROM (read-only)
    MODEL_L = 3
    MODEL_H = 4
    # EPROM (read/write) - Configuration
    ID = 5
    BAUD_RATE = 6
    RETURN_DELAY = 7          # Response delay time (2μs units)
    RESPONSE_STATUS_LEVEL = 8  # Response level
    MIN_ANGLE_LIMIT_L = 9
    MIN_ANGLE_LIMIT_H = 10
    MAX_ANGLE_LIMIT_L = 11
    MAX_ANGLE_LIMIT_H = 12
    MAX_TEMP = 13             # Max temperature limit (°C)
    MAX_VOLTAGE = 14          # Max input voltage (0.1V units)
    MIN_VOLTAGE = 15          # Min input voltage (0.1V units)
    MAX_TORQUE_L = 16         # Max torque limit
    MAX_TORQUE_H = 17
    PHASE = 18                # Magnetic encoder phase
    UNLOADING_CONDITION = 19  # Unloading behavior
    LED_ALARM_CONDITION = 20  # LED alarm triggers
    P_COEFFICIENT = 21        # PID - Proportional
    D_COEFFICIENT = 22        # PID - Derivative
    I_COEFFICIENT = 23        # PID - Integral
    PUNCH_L = 24              # Minimum PWM (startup force)
    PUNCH_H = 25
    CW_DEAD = 26              # Clockwise dead band
    CCW_DEAD = 27             # Counter-clockwise dead band
    PROTECTION_CURRENT_L = 28 # Overload protection current
    PROTECTION_CURRENT_H = 29
    ANGULAR_RESOLUTION = 30   # Position resolution
    OFS_L = 31                # Position offset
    OFS_H = 32
    MODE = 33                 # 0=position, 1=wheel, 2=PWM, 3=step
    PROTECTION_TORQUE = 34    # Overload torque threshold
    PROTECTION_TIME = 35      # Overload time threshold (seconds)
    OVERLOAD_TORQUE = 36      # Startup overload torque
    SPEED_CLOSED_LOOP_P = 37  # Speed loop P coefficient
    OVERCURRENT_TIME = 38     # Overcurrent protection time
    VELOCITY_I = 39           # Speed loop I coefficient
    TORQUE_LIMIT_L = 48       # Torque limit for current position
    TORQUE_LIMIT_H = 49
    CURRENT_L = 50            # Target current limit
    CURRENT_H = 51
    SPINNING_SPEED_L = 52     # Multi-turn spin speed
    SPINNING_SPEED_H = 53
    # SRAM (read/write)
    TORQUE_ENABLE = 40
    ACC = 41                  # Acceleration (0-254)
    GOAL_POSITION_L = 42
    GOAL_POSITION_H = 43
    GOAL_TIME_L = 44
    GOAL_TIME_H = 45
    GOAL_SPEED_L = 46
    GOAL_SPEED_H = 47
    LOCK = 55                 # EPROM lock (STS/SMS series)
    # SRAM (read-only)
    PRESENT_POSITION_L = 56
    PRESENT_POSITION_H = 57
    PRESENT_SPEED_L = 58
    PRESENT_SPEED_H = 59
    PRESENT_LOAD_L = 60
    PRESENT_LOAD_H = 61
    PRESENT_VOLTAGE = 62
    PRESENT_TEMPERATURE = 63
    ASYNC_WRITE_FLAG = 64     # REG_WRITE flag
    SERVO_STATUS = 65         # Status flags (bit0=moving)
    MOVING = 66
    PRESENT_CURRENT_L = 69
    PRESENT_CURRENT_H = 70


BROADCAST_ID = 0xFE  # Send to all servos (no response)


# ============================================================================
# Servo Type Definitions
# ============================================================================

class ServoType:
    """Base class defining servo type characteristics"""
    
    # Type identifier
    name: str = "unknown"
    
    # Byte order: 0=little-endian, 1=big-endian
    endian: int = 0
    
    # Resolution
    resolution_bits: int = 10
    max_position: int = 1023
    
    # Register addresses
    lock_register: int = 48
    id_register: int = 5  # Same for all types
    
    # Feature support
    supports_mode: bool = False
    supports_offset: bool = False
    supports_multi_turn: bool = False
    supports_acceleration: bool = False
    
    # Mode register (if supported)
    mode_register: int = 0
    offset_register: int = 0
    
    @classmethod
    def get_info(cls) -> dict:
        """Return servo type information as dict"""
        return {
            'name': cls.name,
            'endian': cls.endian,
            'resolution_bits': cls.resolution_bits,
            'max_position': cls.max_position,
            'lock_register': cls.lock_register,
            'supports_mode': cls.supports_mode,
            'supports_offset': cls.supports_offset,
            'supports_multi_turn': cls.supports_multi_turn,
            'supports_acceleration': cls.supports_acceleration,
        }


class SCSType(ServoType):
    """SCS series servos (SCS0009, SCS15, SCS215, etc.)"""
    
    name = "scs"
    
    # SCS uses big-endian byte order
    endian = 1
    
    # 10-bit resolution (0-1023 = 0-300°)
    resolution_bits = 10
    max_position = 1023
    
    # Lock register at address 48
    lock_register = SCSReg.LOCK  # 48
    
    # No mode/offset/multi-turn support
    supports_mode = False
    supports_offset = False
    supports_multi_turn = False
    supports_acceleration = False


class STSType(ServoType):
    """STS/SMS series servos (STS3215, SMS_STS, etc.)"""
    
    name = "sts"
    
    # STS uses little-endian byte order
    endian = 0
    
    # 12-bit resolution (0-4095 = 0-360°)
    resolution_bits = 12
    max_position = 4095
    
    # Lock register at address 55
    lock_register = SMSReg.LOCK  # 55
    
    # Full feature support
    supports_mode = True
    supports_offset = True
    supports_multi_turn = True
    supports_acceleration = True
    
    # Feature registers
    mode_register = SMSReg.MODE  # 33
    offset_register = SMSReg.OFS_L  # 31


# Registry of all servo types for easy lookup
SERVO_TYPES: Dict[str, Type[ServoType]] = {
    'scs': SCSType,
    'sts': STSType,
}


def get_servo_type(name: str) -> Type[ServoType]:
    """Get servo type class by name"""
    return SERVO_TYPES.get(name, ServoType)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ServoStatus:
    """Current servo state"""
    id: int
    position: int
    speed: int
    load: int
    voltage: float
    temperature: int
    moving: bool
    current: int


# ============================================================================
# Main Controller Class
# ============================================================================

class FeetechServo:
    """
    Feetech servo controller for macOS
    
    This is the low-level communication class. Use ServoType classes
    to determine correct settings for different servo models.
    
    Example usage:
        servo = FeetechServo()
        servo.open('/dev/tty.usbserial-XXX')
        
        # Detect servo type
        servo_type = servo.detect_type(1)  # Returns 'scs' or 'sts'
        
        # Configure for detected type
        servo.configure_for_type(servo_type)
        
        # Now use the servo
        servo.write_position(1, 512, speed=500)
        
        servo.close()
    """
    
    def __init__(self, end: int = 0, level: int = 1):
        """
        Initialize controller
        
        Args:
            end: Endianness (0=little endian for SMS/STS, 1=big endian for SCS)
            level: Response level (0=no response, 1=respond to all except broadcast)
        """
        self.serial: Optional[serial.Serial] = None
        self.end = end  # Endianness
        self.level = level  # Response level
        self.error = 0  # Last error status
        self.timeout = 0.1  # Read timeout in seconds
        self._servo_type: Optional[Type[ServoType]] = None
    
    def configure_for_type(self, servo_type: str):
        """Configure controller for a specific servo type"""
        type_class = get_servo_type(servo_type)
        self._servo_type = type_class
        self.end = type_class.endian
    
    def get_type_class(self, servo_type: str = None) -> Type[ServoType]:
        """Get the ServoType class for the given type name"""
        if servo_type:
            return get_servo_type(servo_type)
        return self._servo_type or ServoType
    
    # ========================================================================
    # Port Management
    # ========================================================================
    
    # Known USB-serial chip identifiers for servo adapters
    KNOWN_ADAPTERS = [
        'CH340', 'CH341', 'CH343',  # Feetech URT-1, Waveshare (CH343 is newer)
        'CP210', 'CP2102',     # Waveshare, generic
        'FTDI', 'FT232',       # Generic USB-TTL
        'usbserial',           # macOS generic
        'USB Serial', 'USB-Serial', 'USB-Enhanced-SERIAL',  # Windows generic
        'ttyUSB', 'ttyACM',    # Linux generic
        'wchusbserial',        # CH340 macOS driver
        'Prolific',            # PL2303
    ]
    
    @staticmethod
    def find_ports() -> List[dict]:
        """Find available serial ports for servo adapters
        
        Detects:
          - Feetech URT-1 (CH340/CH343)
          - Waveshare Bus Servo Adapter (CH340/CP210x)
          - Other USB-TTL adapters
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            desc_upper = (port.description or '').upper()
            hwid_upper = (port.hwid or '').upper()
            device_upper = port.device.upper()
            
            # Skip Bluetooth and debug ports
            if 'BLUETOOTH' in desc_upper or 'BLUETOOTH' in hwid_upper or 'BTHENUM' in hwid_upper:
                continue
            if 'DEBUG' in device_upper:
                continue
            
            # Check if this looks like a servo adapter
            is_adapter = False
            adapter_type = "Unknown"
            
            for chip in FeetechServo.KNOWN_ADAPTERS:
                chip_upper = chip.upper()
                if chip_upper in desc_upper or chip_upper in hwid_upper or chip_upper in device_upper:
                    is_adapter = True
                    if 'CH343' in desc_upper:
                        adapter_type = "CH343 (URT-1)"
                    elif 'CH340' in desc_upper or 'CH341' in desc_upper:
                        adapter_type = "CH340 (URT-1/Waveshare)"
                    elif 'CP210' in desc_upper:
                        adapter_type = "CP210x (Waveshare)"
                    elif 'FTDI' in desc_upper or 'FT232' in desc_upper:
                        adapter_type = "FTDI"
                    else:
                        adapter_type = chip
                    break
            
            ports.append({
                'device': port.device,
                'description': port.description,
                'hwid': port.hwid,
                'is_adapter': is_adapter,
                'adapter_type': adapter_type
            })
            
            marker = "*" if is_adapter else " "
            print(f"  {marker} {port.device}: {port.description} [{adapter_type}]")
        
        return ports
    
    @staticmethod
    def auto_detect_port() -> Optional[str]:
        """Auto-detect the best serial port for servo communication"""
        for port in serial.tools.list_ports.comports():
            desc = (port.description or '').upper()
            hwid = (port.hwid or '').upper()
            device = port.device.upper()
            
            # Check for known adapter chips
            for chip in FeetechServo.KNOWN_ADAPTERS:
                if chip.upper() in desc or chip.upper() in hwid or chip.upper() in device:
                    return port.device
        
        return None
    
    def open(self, port: str, baudrate: int = 1000000) -> bool:
        """
        Open serial connection to URT-1 debugger
        
        Args:
            port: Serial port path (e.g., '/dev/tty.usbserial-1410')
            baudrate: Communication speed (default 1000000 for most servos)
        
        Returns:
            True if connection successful
        """
        try:
            self.serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            return True
        except serial.SerialException as e:
            print(f"Error opening port: {e}")
            return False
    
    def close(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
    
    def set_baudrate(self, baudrate: int):
        """Change communication baud rate"""
        if self.serial:
            self.serial.baudrate = baudrate
    
    # ========================================================================
    # Low-Level Protocol
    # ========================================================================
    
    def _host2scs(self, data: int) -> Tuple[int, int]:
        """Split 16-bit value into two bytes based on endianness"""
        if self.end:  # Big endian
            return (data >> 8) & 0xFF, data & 0xFF
        else:  # Little endian
            return data & 0xFF, (data >> 8) & 0xFF
    
    def _scs2host(self, low: int, high: int) -> int:
        """Combine two bytes into 16-bit value based on endianness"""
        if self.end:  # Big endian
            return (low << 8) | high
        else:  # Little endian
            return (high << 8) | low
    
    def _write_buf(self, servo_id: int, mem_addr: int, data: bytes, instruction: int):
        """Build and send instruction packet"""
        if data:
            msg_len = len(data) + 3  # Length includes instruction + address + data + checksum
            packet = bytes([0xFF, 0xFF, servo_id, msg_len, instruction, mem_addr]) + data
        else:
            msg_len = 2
            packet = bytes([0xFF, 0xFF, servo_id, msg_len, instruction])
        
        # Calculate checksum
        checksum = servo_id + msg_len + instruction
        if data:
            checksum += mem_addr + sum(data)
        checksum = (~checksum) & 0xFF
        
        packet += bytes([checksum])
        self.serial.write(packet)
        self.serial.flush()
    
    def _check_head(self) -> bool:
        """Check for response header (0xFF 0xFF)"""
        buf = [0, 0]
        cnt = 0
        while True:
            data = self.serial.read(1)
            if not data:
                return False
            buf[1] = buf[0]
            buf[0] = data[0]
            if buf[0] == 0xFF and buf[1] == 0xFF:
                return True
            cnt += 1
            if cnt > 10:
                return False
    
    def _ack(self, servo_id: int) -> bool:
        """Wait for and validate acknowledgment"""
        self.error = 0
        if servo_id != BROADCAST_ID and self.level:
            if not self._check_head():
                return False
            
            buf = self.serial.read(4)
            if len(buf) != 4:
                return False
            
            if buf[0] != servo_id:
                return False
            if buf[1] != 2:
                return False
            
            calc_sum = (~(buf[0] + buf[1] + buf[2])) & 0xFF
            if calc_sum != buf[3]:
                return False
            
            self.error = buf[2]
        return True
    
    # ========================================================================
    # Basic Commands
    # ========================================================================
    
    def ping(self, servo_id: int) -> int:
        """
        Ping servo to check if it's connected
        
        Args:
            servo_id: Servo ID (1-253) or 0xFE for broadcast
        
        Returns:
            Servo ID if found, -1 if not found
        """
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, 0, None, Instruction.PING)
        
        self.error = 0
        if not self._check_head():
            return -1
        
        buf = self.serial.read(4)
        if len(buf) != 4:
            return -1
        
        if buf[0] != servo_id and servo_id != BROADCAST_ID:
            return -1
        if buf[1] != 2:
            return -1
        
        calc_sum = (~(buf[0] + buf[1] + buf[2])) & 0xFF
        if calc_sum != buf[3]:
            return -1
        
        self.error = buf[2]
        return buf[0]
    
    def scan(self, start_id: int = 1, end_id: int = 253) -> List[int]:
        """
        Scan for connected servos
        
        Args:
            start_id: Starting ID to scan
            end_id: Ending ID to scan
        
        Returns:
            List of found servo IDs
        """
        found = []
        old_timeout = self.timeout
        self.serial.timeout = 0.01  # Short timeout for scanning
        
        for servo_id in range(start_id, end_id + 1):
            result = self.ping(servo_id)
            if result >= 0:
                found.append(result)
                print(f"  Found servo ID: {result}")
        
        self.serial.timeout = old_timeout
        return found
    
    def detect_type(self, servo_id: int) -> str:
        """
        Detect servo type (SCS or STS) by reading registers
        
        Returns:
            'scs' or 'sts'
        """
        # Save current endianness
        old_end = self.end
        
        # Try reading max limit with little-endian (STS default)
        self.end = 0
        max_limit = self.read_word(servo_id, SCSReg.MAX_ANGLE_LIMIT_L)
        
        # If max limit is impossibly high (> 4096), we're reading with wrong endianness
        # This means it's an SCS servo that needs big-endian
        if max_limit > 4096:
            self.end = old_end
            return 'scs'
        
        # If max limit is around 4095, it's likely STS (12-bit)
        if max_limit > 1500:
            self.end = old_end
            return 'sts'
        
        # Check lock registers to confirm
        lock_48 = self.read_byte(servo_id, SCSReg.LOCK)  # SCS lock at 48
        lock_55 = self.read_byte(servo_id, SMSReg.LOCK)  # STS lock at 55
        
        self.end = old_end
        
        # SCS: lock at 48 is typically 1 (locked)
        if lock_48 == 1 and lock_55 != 1:
            return 'scs'
        
        return 'sts'
    
    # ========================================================================
    # Read/Write Operations
    # ========================================================================
    
    def write_byte(self, servo_id: int, address: int, value: int) -> bool:
        """Write single byte to servo memory"""
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, bytes([value & 0xFF]), Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_word(self, servo_id: int, address: int, value: int) -> bool:
        """Write 16-bit word to servo memory"""
        low, high = self._host2scs(value)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_bytes(self, servo_id: int, address: int, data: bytes) -> bool:
        """Write multiple bytes to servo memory"""
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    def read_bytes(self, servo_id: int, address: int, length: int) -> Optional[bytes]:
        """Read bytes from servo memory"""
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, bytes([length]), Instruction.READ)
        
        if not self._check_head():
            return None
        
        self.error = 0
        header = self.serial.read(3)
        if len(header) != 3:
            return None
        
        data = self.serial.read(length)
        if len(data) != length:
            return None
        
        checksum = self.serial.read(1)
        if len(checksum) != 1:
            return None
        
        # Verify checksum
        calc_sum = header[0] + header[1] + header[2] + sum(data)
        calc_sum = (~calc_sum) & 0xFF
        if calc_sum != checksum[0]:
            return None
        
        self.error = header[2]
        return data
    
    def read_byte(self, servo_id: int, address: int) -> int:
        """Read single byte from servo memory"""
        data = self.read_bytes(servo_id, address, 1)
        if data:
            return data[0]
        return -1
    
    def read_word(self, servo_id: int, address: int) -> int:
        """Read 16-bit word from servo memory"""
        data = self.read_bytes(servo_id, address, 2)
        if data:
            return self._scs2host(data[0], data[1])
        return -1
    
    # ========================================================================
    # High-Level Servo Control
    # ========================================================================
    
    def write_position(self, servo_id: int, position: int, time_ms: int = 0, speed: int = 0) -> bool:
        """
        Move servo to position
        
        Args:
            servo_id: Servo ID
            position: Target position (can be signed for multi-turn mode)
            time_ms: Movement time in milliseconds (0 = use speed)
            speed: Maximum speed in steps/second (0 = maximum)
        
        Returns:
            True if command sent successfully
        """
        # Handle signed position for multi-turn mode
        if position < 0:
            position = 0x10000 + position
        
        pos_l, pos_h = self._host2scs(position & 0xFFFF)
        time_l, time_h = self._host2scs(time_ms)
        speed_l, speed_h = self._host2scs(speed)
        
        data = bytes([pos_l, pos_h, time_l, time_h, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, SCSReg.GOAL_POSITION_L, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    def read_position(self, servo_id: int) -> int:
        """Read current position (unsigned)"""
        return self.read_word(servo_id, SCSReg.PRESENT_POSITION_L)
    
    def read_position_signed(self, servo_id: int) -> int:
        """Read current position as signed value (for multi-turn mode)"""
        pos = self.read_word(servo_id, SCSReg.PRESENT_POSITION_L)
        if pos >= 0:
            return pos if pos < 32768 else pos - 65536
        return pos
    
    def read_word_signed(self, servo_id: int, address: int) -> int:
        """Read 16-bit signed value from servo memory"""
        val = self.read_word(servo_id, address)
        if val >= 0:
            return val if val < 32768 else val - 65536
        return val
    
    def read_speed(self, servo_id: int) -> int:
        """Read current speed (signed - negative means reverse direction)"""
        speed = self.read_word(servo_id, SCSReg.PRESENT_SPEED_L)
        if speed >= 0:
            return speed if speed < 32768 else speed - 65536
        return speed
    
    def read_load(self, servo_id: int) -> int:
        """Read current load (bit 10 = direction, bits 0-9 = magnitude 0-1023)"""
        return self.read_word(servo_id, SCSReg.PRESENT_LOAD_L)
    
    def read_voltage(self, servo_id: int) -> float:
        """Read current voltage in volts"""
        v = self.read_byte(servo_id, SCSReg.PRESENT_VOLTAGE)
        if v >= 0:
            return v / 10.0
        return -1
    
    def read_temperature(self, servo_id: int) -> int:
        """Read current temperature in Celsius"""
        return self.read_byte(servo_id, SCSReg.PRESENT_TEMPERATURE)
    
    def is_moving(self, servo_id: int) -> bool:
        """Check if servo is currently moving"""
        return self.read_byte(servo_id, SCSReg.MOVING) == 1
    
    def read_current(self, servo_id: int) -> int:
        """Read current in mA"""
        val = self.read_word(servo_id, SCSReg.PRESENT_CURRENT_L)
        if val >= 0:
            return val * 6.5  # Convert to mA
        return -1
    
    def enable_torque(self, servo_id: int, enable: bool = True) -> bool:
        """Enable or disable servo torque"""
        return self.write_byte(servo_id, SCSReg.TORQUE_ENABLE, 1 if enable else 0)
    
    def disable_torque(self, servo_id: int) -> bool:
        """Disable servo torque (servo can be moved by hand)"""
        return self.enable_torque(servo_id, False)
    
    def get_status(self, servo_id: int) -> Optional[ServoStatus]:
        """Read all servo status in one transaction"""
        # Read 15 bytes starting from PRESENT_POSITION_L
        data = self.read_bytes(servo_id, SCSReg.PRESENT_POSITION_L, 15)
        if not data:
            return None
        
        return ServoStatus(
            id=servo_id,
            position=self._scs2host(data[0], data[1]),
            speed=self._scs2host(data[2], data[3]),
            load=self._scs2host(data[4], data[5]),
            voltage=data[6] / 10.0,
            temperature=data[7],
            moving=data[10] == 1,
            current=self._scs2host(data[13], data[14]) * 6.5
        )
    
    # ========================================================================
    # Servo Configuration (Type-Aware)
    # ========================================================================
    
    def unlock_eprom(self, servo_id: int, servo_type: str = None) -> bool:
        """
        Unlock EPROM for writing (required before changing ID, etc.)
        
        Args:
            servo_id: The servo ID
            servo_type: 'scs' or 'sts' - uses correct lock register
        """
        type_class = self.get_type_class(servo_type)
        return self.write_byte(servo_id, type_class.lock_register, 0)
    
    def lock_eprom(self, servo_id: int, servo_type: str = None) -> bool:
        """
        Lock EPROM after writing (saves changes to flash)
        
        Args:
            servo_id: The servo ID
            servo_type: 'scs' or 'sts' - uses correct lock register
        """
        type_class = self.get_type_class(servo_type)
        return self.write_byte(servo_id, type_class.lock_register, 1)
    
    def set_id(self, servo_id: int, new_id: int, servo_type: str = None) -> bool:
        """
        Change servo ID
        
        WARNING: This changes permanent settings. Use carefully!
        """
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        result = self.write_byte(servo_id, SCSReg.ID, new_id)  # ID register is same for all
        self.lock_eprom(new_id, servo_type)  # Lock with new ID
        return result
    
    def set_angle_limits(self, servo_id: int, min_angle: int, max_angle: int, servo_type: str = None) -> bool:
        """Set servo angle limits"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        self.write_word(servo_id, SCSReg.MIN_ANGLE_LIMIT_L, min_angle)
        self.write_word(servo_id, SCSReg.MAX_ANGLE_LIMIT_L, max_angle)
        
        return self.lock_eprom(servo_id, servo_type)
    
    def set_baud_rate(self, servo_id: int, baud_index: int, servo_type: str = None) -> bool:
        """Set servo baud rate (0-7, see BaudRate enum)"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        result = self.write_byte(servo_id, SCSReg.BAUD_RATE, baud_index)
        self.lock_eprom(servo_id, servo_type)
        return result
    
    # ========================================================================
    # STS-Specific Features
    # ========================================================================
    
    def set_mode(self, servo_id: int, mode: int) -> bool:
        """
        Set servo mode (STS/SMS only)
        
        Modes: 0=Position, 1=Wheel, 2=PWM, 3=Step
        """
        type_class = self.get_type_class('sts')
        if not type_class.supports_mode:
            return False
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
        result = self.write_byte(servo_id, type_class.mode_register, mode)
        self.lock_eprom(servo_id, 'sts')
        return result
    
    def set_offset(self, servo_id: int, offset: int) -> bool:
        """
        Set position offset (STS/SMS only)
        
        Args:
            offset: Signed offset value
        """
        type_class = self.get_type_class('sts')
        if not type_class.supports_offset:
            return False
        
        # Convert signed to unsigned
        if offset < 0:
            offset = offset + 65536
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
        result = self.write_word(servo_id, type_class.offset_register, offset)
        self.lock_eprom(servo_id, 'sts')
        return result
    
    def write_position_with_acc(self, servo_id: int, position: int, speed: int, acc: int = 0) -> bool:
        """
        Move servo to position with acceleration control (STS/SMS only)
        
        Args:
            servo_id: Servo ID
            position: Target position (can be signed for multi-turn)
            speed: Movement speed
            acc: Acceleration (0=max)
        """
        # Handle signed position
        if position < 0:
            position = 0x10000 + position
        
        pos_l, pos_h = self._host2scs(position & 0xFFFF)
        speed_l, speed_h = self._host2scs(speed)
        
        data = bytes([acc, pos_l, pos_h, 0, 0, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, SMSReg.ACC, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_wheel_speed(self, servo_id: int, speed: int, acc: int = 0) -> bool:
        """
        Write wheel speed (STS/SMS only, requires wheel mode)
        
        Args:
            speed: Speed value (-32767 to 32767)
            acc: Acceleration
        """
        if speed < 0:
            speed = 0x10000 + speed
        
        speed_l, speed_h = self._host2scs(speed & 0xFFFF)
        data = bytes([acc, 0, 0, 0, 0, speed_l, speed_h])
        
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, SMSReg.ACC, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    # ========================================================================
    # PWM Mode
    # ========================================================================
    
    def pwm_mode(self, servo_id: int, servo_type: str = None) -> bool:
        """Switch to PWM output mode"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        self.write_word(servo_id, SCSReg.MIN_ANGLE_LIMIT_L, 0)
        self.write_word(servo_id, SCSReg.MAX_ANGLE_LIMIT_L, 0)
        
        return self.lock_eprom(servo_id, servo_type)
    
    def write_pwm(self, servo_id: int, pwm: int) -> bool:
        """
        Write PWM output (-1000 to 1000)
        
        Requires PWM mode to be enabled first.
        """
        if pwm < 0:
            pwm = 0x10000 + pwm  # Two's complement for negative
        
        low, high = self._host2scs(pwm & 0xFFFF)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, SCSReg.GOAL_TIME_L, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)
    
    # ========================================================================
    # Sync Write (multiple servos at once)
    # ========================================================================
    
    def sync_write_position(self, servos: List[Tuple[int, int, int, int]]):
        """
        Write position to multiple servos simultaneously
        
        Args:
            servos: List of (id, position, time_ms, speed) tuples
        """
        if not servos:
            return
        
        self.serial.reset_input_buffer()
        
        # Build sync write packet
        data_len = 6  # 2 bytes each for position, time, speed
        msg_len = (data_len + 1) * len(servos) + 4
        
        packet = bytes([0xFF, 0xFF, BROADCAST_ID, msg_len, Instruction.SYNC_WRITE,
                       SCSReg.GOAL_POSITION_L, data_len])
        
        checksum = BROADCAST_ID + msg_len + Instruction.SYNC_WRITE + SCSReg.GOAL_POSITION_L + data_len
        
        for servo_id, position, time_ms, speed in servos:
            pos_l, pos_h = self._host2scs(position)
            time_l, time_h = self._host2scs(time_ms)
            speed_l, speed_h = self._host2scs(speed)
            
            servo_data = bytes([servo_id, pos_l, pos_h, time_l, time_h, speed_l, speed_h])
            packet += servo_data
            checksum += sum(servo_data)
        
        checksum = (~checksum) & 0xFF
        packet += bytes([checksum])
        
        self.serial.write(packet)
        self.serial.flush()


# ============================================================================
# Convenience Classes (Preconfigured for specific servo types)
# ============================================================================

class SCSController(FeetechServo):
    """
    Preconfigured controller for SCS series servos (SCS0009, SCS15, SCS215, etc.)
    
    Position range: 0-1023 (10-bit) = 0-300°
    """
    
    def __init__(self, level: int = 1):
        super().__init__(end=1, level=level)  # Big endian for SCS series
        self._servo_type = SCSType


class STSController(FeetechServo):
    """
    Preconfigured controller for STS/SMS series servos (STS3215, SMS_STS, etc.)
    
    Position range: 0-4095 (12-bit) = 0-360°
    Multi-turn: Supports negative positions
    """
    
    def __init__(self, level: int = 1):
        super().__init__(end=0, level=level)  # Little endian for SMS/STS
        self._servo_type = STSType


# Keep old names for backwards compatibility
FeetechSCS = SCSController
FeetechSMS = STSController


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Feetech Servo Controller')
    parser.add_argument('--port', '-p', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--baud', '-b', type=int, default=1000000, help='Baud rate')
    parser.add_argument('--scan', action='store_true', help='Scan for servos')
    parser.add_argument('--ping', type=int, help='Ping specific servo ID')
    parser.add_argument('--id', type=int, help='Servo ID for commands')
    parser.add_argument('--pos', type=int, help='Move to position')
    parser.add_argument('--speed', type=int, default=0, help='Movement speed')
    parser.add_argument('--status', action='store_true', help='Read servo status')
    parser.add_argument('--list', action='store_true', help='List serial ports')
    parser.add_argument('--type', choices=['scs', 'sts'], help='Servo type (auto-detect if not specified)')
    
    args = parser.parse_args()
    
    if args.list:
        print("Available serial ports:")
        FeetechServo.find_ports()
        return
    
    servo = FeetechServo()
    
    if not args.port:
        print("Available serial ports:")
        ports = FeetechServo.find_ports()
        if not ports:
            print("No serial ports found!")
            return
        
        # Try to auto-detect adapter
        args.port = FeetechServo.auto_detect_port()
        if args.port:
            print(f"\nAuto-selected: {args.port}")
        else:
            print("\nNo servo adapter detected. Please specify a port with --port")
            return
    
    if not servo.open(args.port, args.baud):
        print(f"Failed to open {args.port}")
        return
    
    print(f"Connected to {args.port} at {args.baud} baud")
    
    try:
        if args.scan:
            print("Scanning for servos...")
            found = servo.scan()
            print(f"Found {len(found)} servo(s): {found}")
            
            # Detect type of first found servo
            if found:
                servo_type = servo.detect_type(found[0])
                print(f"Servo {found[0]} detected as: {servo_type.upper()}")
        
        elif args.ping is not None:
            result = servo.ping(args.ping)
            if result >= 0:
                print(f"Servo {result} responded!")
                servo_type = servo.detect_type(result)
                print(f"Detected type: {servo_type.upper()}")
            else:
                print(f"No response from servo {args.ping}")
        
        elif args.id is not None:
            # Detect or use specified type
            servo_type = args.type or servo.detect_type(args.id)
            servo.configure_for_type(servo_type)
            print(f"Using servo type: {servo_type.upper()}")
            
            if args.pos is not None:
                print(f"Moving servo {args.id} to position {args.pos}")
                servo.write_position(args.id, args.pos, speed=args.speed)
            
            if args.status:
                status = servo.get_status(args.id)
                if status:
                    print(f"Servo {status.id} Status:")
                    print(f"  Position: {status.position}")
                    print(f"  Speed: {status.speed}")
                    print(f"  Load: {status.load}")
                    print(f"  Voltage: {status.voltage}V")
                    print(f"  Temperature: {status.temperature}°C")
                    print(f"  Moving: {status.moving}")
                    print(f"  Current: {status.current:.1f}mA")
                else:
                    print("Failed to read status")
        else:
            print("No command specified. Use --help for options.")
    
    finally:
        servo.close()


if __name__ == '__main__':
    main()

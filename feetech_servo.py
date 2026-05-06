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
from servo_mappings import SCS_MEMORY_MAP, STS_MEMORY_MAP

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


# Common register addresses used internally for protocol commands
REG_ID = 5
REG_BAUD_RATE = 6
REG_MIN_ANGLE = 9
REG_MAX_ANGLE = 11
REG_OFFSET = 31
REG_MODE = 33
REG_TORQUE_ENABLE = 40
REG_ACC = 41
REG_GOAL_POSITION = 42
REG_GOAL_TIME = 44
REG_GOAL_SPEED = 46
REG_LOCK_SCS = 48
REG_LOCK_STS = 55
REG_PRESENT_POSITION = 56
REG_PRESENT_SPEED = 58
REG_PRESENT_LOAD = 60
REG_PRESENT_VOLTAGE = 62
REG_PRESENT_TEMPERATURE = 63
REG_MOVING = 66
REG_PRESENT_CURRENT = 69


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
    lock_register = REG_LOCK_SCS  # 48
    
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
    lock_register = REG_LOCK_STS  # 55
    
    # Full feature support
    supports_mode = True
    supports_offset = True
    supports_multi_turn = True
    supports_acceleration = True
    
    # Feature registers
    mode_register = REG_MODE  # 33
    offset_register = REG_OFFSET  # 31


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
    
    def _to_sign_magnitude(self, value: int, sign_bit: int = 15) -> int:
        """
        Convert signed integer to sign-magnitude encoding.
        
        Per official Feetech SDK: negative values use bit at 'sign_bit' position
        for the sign, with remaining bits as magnitude.
        
        Examples with sign_bit=15:
          100 -> 100 (0x0064)
          -100 -> 32868 (0x8064 = 0x8000 | 100)
        
        Args:
            value: Signed integer to convert
            sign_bit: Bit position for sign (15 for position, 10 for speed/PWM)
        
        Returns:
            Sign-magnitude encoded value
        
        Note: Values are clamped to valid range to prevent encoding errors.
              For sign_bit=15: -32767 to +32767
              For sign_bit=10: -1023 to +1023
        """
        max_magnitude = (1 << sign_bit) - 1  # 32767 for bit 15, 1023 for bit 10
        
        if value < 0:
            magnitude = min(-value, max_magnitude)
            return magnitude | (1 << sign_bit)
        else:
            return min(value, max_magnitude)
    
    def _from_sign_magnitude(self, value: int, sign_bit: int = 15) -> int:
        """
        Convert sign-magnitude encoding to signed integer.
        
        Per official Feetech SDK: bit at 'sign_bit' indicates negative,
        remaining bits are magnitude.
        
        Args:
            value: Sign-magnitude encoded value
            sign_bit: Bit position for sign (15 for position, 10 for speed)
        
        Returns:
            Signed integer
        """
        if value & (1 << sign_bit):
            return -(value & ~(1 << sign_bit))
        return value
    
    def read_register(self, servo_id: int, address: int) -> int:
        """Read a register using the size and signedness from the servo type map"""
        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        
        reg_info = memory_map.get(address)
        if not reg_info:
            # Fallback for reading unknown regs
            return self.read_byte(servo_id, address)
            
        size = reg_info['size']
        signed_bit = reg_info.get('signed_bit')
        
        if size == 1:
            val = self.read_byte(servo_id, address)
        else:
            val = self.read_word(servo_id, address)
            
        if val >= 0 and signed_bit is not None:
            return self._from_sign_magnitude(val, signed_bit)
            
        return val

    def write_register(self, servo_id: int, address: int, value: int) -> bool:
        """Write a register using the size and signedness from the servo type map"""
        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        
        reg_info = memory_map.get(address)
        if not reg_info:
            return False
            
        size = reg_info['size']
        signed_bit = reg_info.get('signed_bit')
        
        # FIX: Only apply sign_magnitude if signed_bit is explicit, EXCEPT for SCS speed if needed
        # but the map handles STS ones perfectly.
        if signed_bit is not None:
            value = self._to_sign_magnitude(value, signed_bit)
            
        if size == 1:
            return self.write_byte(servo_id, address, value)
        else:
            return self.write_word(servo_id, address, value)
    
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
        Best-effort servo type detection.  Results can be overridden by the
        caller (e.g. from a user-selected type in the GUI).

        Strategy:
        1. Lock registers — SCS has LOCK at 48, STS has LOCK at 55.
        2. STS-only registers — STS defines MODE(33), OFS(31-32),
           ACCELERATION(41) which SCS doesn't.  Read a block and check
           if the STS-extended range (49-54) holds non-zero EPROM data
           that only STS would have.
        3. Position / angle range — SCS is 10-bit (0-1023), STS is
           12-bit (0-4095).  Try both endiannesses on raw bytes.
        4. Default to SCS when ambiguous.

        Returns:
            'scs' or 'sts'
        """
        old_end = self.end

        # --- Lock registers (decisive when unambiguous) ---
        lock_55 = self.read_byte(servo_id, REG_LOCK_STS)
        lock_48 = self.read_byte(servo_id, REG_LOCK_SCS)

        if lock_55 in (0, 1) and lock_48 not in (0, 1):
            self.end = old_end
            return 'sts'
        if lock_48 in (0, 1) and lock_55 not in (0, 1):
            self.end = old_end
            return 'scs'

        # --- STS-extended EPROM range (addrs 49-54) ---
        # On STS these are part of the EPROM (speed-PID, torque-on-boot, etc.)
        # and often hold non-zero factory defaults.
        # On SCS, addrs 49-54 are past the EPROM boundary (LOCK=48) and are
        # undefined RAM that reads as 0 after power-cycle.
        extended = self.read_bytes(servo_id, 49, 6)  # addrs 49-54
        if extended and len(extended) == 6:
            if any(b != 0 for b in extended):
                self.end = old_end
                return 'sts'

        # --- Voting across position / angle registers ---
        scs_votes = 0
        sts_votes = 0

        for addr in (REG_PRESENT_POSITION, REG_MIN_ANGLE, REG_MAX_ANGLE):
            raw = self.read_bytes(servo_id, addr, 2)
            if not raw or len(raw) != 2:
                continue
            val_be = (raw[0] << 8) | raw[1]
            val_le = (raw[1] << 8) | raw[0]
            be_ok = 0 <= val_be <= 1023
            le_ok = 0 <= val_le <= 4095
            if be_ok and not le_ok:
                scs_votes += 1
            elif le_ok and not be_ok:
                sts_votes += 1

        self.end = old_end

        if scs_votes > sts_votes:
            return 'scs'
        if sts_votes > scs_votes:
            return 'sts'

        return 'scs'
    
    # ========================================================================
    # Read/Write Operations
    # ========================================================================
    
    def write_byte(self, servo_id: int, address: int, value: int) -> bool:
        """Write single byte to servo memory"""
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, bytes([value & 0xFF]), Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_word(self, servo_id: int, address: int, value: int) -> bool:
        """Write 16-bit word to servo memory (unsigned)"""
        low, high = self._host2scs(value & 0xFFFF)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, address, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_word_signed(self, servo_id: int, address: int, value: int) -> bool:
        """Write 16-bit signed word using sign-magnitude encoding (for STS/SMS).
        
        Per official Feetech SDK:
        - Negative values: bit 15 = 1, bits 0-14 = magnitude
        - Positive values: bit 15 = 0, bits 0-14 = value
        
        Use this for angle limits, offsets, and other signed EPROM values on STS/SMS.
        """
        encoded = self._to_sign_magnitude(value, 15)
        low, high = self._host2scs(encoded)
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
        """Move servo to position"""
        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        
        reg_info = memory_map.get(REG_GOAL_POSITION)
        if reg_info and reg_info.get('signed_bit') is not None:
            position = self._to_sign_magnitude(position, reg_info['signed_bit'])
        else:
            if position < 0:
                position = 0x10000 + position
            position = max(0, min(0xFFFF, position))
            
        pos_l, pos_h = self._host2scs(position)
        
        # SCS doesn't have multi-turn or sign-magnitude for speed/time here typically
        # And STS docs say these time/speed args in GOAL_POSITION write are unsigned magnitude
        time_l, time_h = self._host2scs(time_ms & 0xFFFF)
        speed_l, speed_h = self._host2scs(speed & 0xFFFF)
        
        data = bytes([pos_l, pos_h, time_l, time_h, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_POSITION, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    def read_position(self, servo_id: int) -> int:
        """Read current position."""
        return self.read_register(servo_id, REG_PRESENT_POSITION)
    
    def read_position_signed(self, servo_id: int) -> int:
        """
        Read current position as signed value (for multi-turn mode).
        
        Note: The Feetech STS documentation indicates that position uses
        Two's Complement for negative values (not Sign-Magnitude like speed).
        """
        pos = self.read_position(servo_id)
        if pos >= 0:
            return pos if pos < 32768 else pos - 65536
        return pos
    
    def read_word_signed(self, servo_id: int, address: int) -> int:
        """Read value with automatic decoding from servo map."""
        return self.read_register(servo_id, address)
    
    def read_speed(self, servo_id: int) -> int:
        """Read current speed."""
        val = self.read_register(servo_id, REG_PRESENT_SPEED)
        # STS auto-decodes via signed_bit map, SCS doesn't. 
        # But wait, does SCS also use bit 15 for speed sign?
        # The previous code did: self._from_sign_magnitude(speed, 15) unconditionally for read_speed!
        if val >= 0 and self.get_type_class().name == 'scs':
             # The new servo_mappings.py didn't set signed_bit for SCS speed!
             return self._from_sign_magnitude(val, 15)
        return val
    
    def read_load(self, servo_id: int) -> int:
        """Read current load (bit 10 = direction, bits 0-9 = magnitude 0-1023)."""
        return self.read_register(servo_id, REG_PRESENT_LOAD)
    
    def read_voltage(self, servo_id: int) -> float:
        """Read current voltage in volts"""
        v = self.read_register(servo_id, REG_PRESENT_VOLTAGE)
        if v >= 0:
            return v / 10.0
        return -1
    
    def read_temperature(self, servo_id: int) -> int:
        """Read current temperature in Celsius"""
        return self.read_register(servo_id, REG_PRESENT_TEMPERATURE)
    
    def is_moving(self, servo_id: int) -> bool:
        """Check if servo is currently moving"""
        return self.read_register(servo_id, REG_MOVING) == 1
    
    def read_current(self, servo_id: int) -> int:
        """Read current in mA"""
        val = self.read_register(servo_id, REG_PRESENT_CURRENT)
        if val >= 0:
            return val * 6.5  # Convert to mA
        return -1
    
    def enable_torque(self, servo_id: int, enable: bool = True) -> bool:
        """Enable or disable servo torque"""
        return self.write_byte(servo_id, REG_TORQUE_ENABLE, 1 if enable else 0)
    
    def disable_torque(self, servo_id: int) -> bool:
        """Disable servo torque (servo can be moved by hand)"""
        return self.enable_torque(servo_id, False)
    
    def get_status(self, servo_id: int) -> Optional[ServoStatus]:
        """Read all servo status in one transaction"""
        # Read 15 bytes starting from PRESENT_POSITION_L
        data = self.read_bytes(servo_id, REG_PRESENT_POSITION, 15)
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
        result = self.write_byte(servo_id, REG_ID, new_id)  # ID register is same for all
        self.lock_eprom(new_id, servo_type)  # Lock with new ID
        return result
    
    def set_angle_limits(self, servo_id: int, min_angle: int, max_angle: int, servo_type: str = None) -> bool:
        """Set servo angle limits"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        # write_register uses the memory map to automatically figure out sizes and sign encoding
        self.write_register(servo_id, REG_MIN_ANGLE, min_angle)
        self.write_register(servo_id, REG_MAX_ANGLE, max_angle)
        
        return self.lock_eprom(servo_id, servo_type)
    
    def set_baud_rate(self, servo_id: int, baud_index: int, servo_type: str = None) -> bool:
        """Set servo baud rate (0-7, see BaudRate enum)"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        result = self.write_byte(servo_id, REG_BAUD_RATE, baud_index)
        self.lock_eprom(servo_id, servo_type)
        return result
    
    # ========================================================================
    # STS-Specific Features
    # ========================================================================
    
    def set_mode(self, servo_id: int, mode: int) -> bool:
        """
        Set servo mode (STS/SMS only)
        
        Modes: 0=Position, 1=Wheel, 2=PWM, 3=Multi-turn
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
        """Set position offset (STS/SMS only). Keeps absolute position fixed."""
        type_class = self.get_type_class('sts')
        if not type_class.supports_offset:
            return False
            
        # Offset must be positive
        offset = max(0, offset)
        
        # Read current torque state
        torque_enabled = self.read_register(servo_id, REG_TORQUE_ENABLE) == 1
        
        if torque_enabled:
            # Disabling torque allows the offset to change without the servo immediately
            # trying to physically move to maintain its old goal position.
            self.disable_torque(servo_id)
            time.sleep(0.05)
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
            
        result = self.write_register(servo_id, type_class.offset_register, offset)
        self.lock_eprom(servo_id, 'sts')
        
        if torque_enabled:
            # Re-enabling torque causes the Feetech firmware to automatically
            # set its internal Goal Position to its new Present Position,
            # meaning it will securely hold its current physical angle without twitching.
            time.sleep(0.05)
            self.enable_torque(servo_id)
            
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
        # Handle signed position (Two's Complement)
        if position < 0:
            position = 0x10000 + position
        position = max(0, min(0xFFFF, position))
        
        pos_l, pos_h = self._host2scs(position)
        speed_l, speed_h = self._host2scs(speed)
        
        data = bytes([acc, pos_l, pos_h, 0, 0, speed_l, speed_h])
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_ACC, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    def write_wheel_speed(self, servo_id: int, speed: int, acc: int = 0) -> bool:
        """
        Write wheel speed (STS/SMS only, requires wheel mode)
        
        Args:
            speed: Speed value (-32767 to 32767)
            acc: Acceleration
        
        Note: Uses sign-magnitude with bit 15 per official SDK
        """
        speed = self._to_sign_magnitude(speed, 15)
        
        speed_l, speed_h = self._host2scs(speed & 0xFFFF)
        data = bytes([acc, 0, 0, 0, 0, speed_l, speed_h])
        
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_ACC, data, Instruction.WRITE)
        return self._ack(servo_id)
    
    # ========================================================================
    # PWM Mode
    # ========================================================================
    
    def pwm_mode(self, servo_id: int, servo_type: str = None) -> bool:
        """Switch to PWM output mode"""
        if not self.unlock_eprom(servo_id, servo_type):
            return False
        
        self.write_word(servo_id, REG_MIN_ANGLE, 0)
        self.write_word(servo_id, REG_MAX_ANGLE, 0)
        
        return self.lock_eprom(servo_id, servo_type)
    
    def write_pwm(self, servo_id: int, pwm: int) -> bool:
        """Write PWM output"""
        return self.write_register(servo_id, REG_GOAL_TIME, pwm)
    
    # ========================================================================
    # Step Mode (Multi-turn / Continuous Position Mode)
    # ========================================================================
    
    def enable_step_mode(self, servo_id: int, speed: int = 300, acc: int = 50) -> bool:
        """
        Configure servo for step mode (Mode 3).
        
        In step mode, the goal position register becomes an INCREMENTAL delta:
        - Each write moves the servo by that many steps
        - Positive = one direction, negative = opposite direction
        - Uses sign-magnitude encoding (bit 15 = direction)
        
        Per Feetech docs: "set the maximum angle and minimum angle to '0' 
        and the operation mode to '3'"
        
        Args:
            servo_id: Servo ID
            speed: Movement speed (set once, applied to all steps)
            acc: Acceleration value
            
        Returns:
            True if successful
        """
        # Torque off for mode change
        self.write_byte(servo_id, REG_TORQUE_ENABLE, 0)
        time.sleep(0.05)
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
        
        # Set mode 3 (step/multi-turn)
        self.write_byte(servo_id, REG_MODE, 3)
        
        # Limits MUST be 0,0 for step mode
        self.write_word(servo_id, REG_MIN_ANGLE, 0)
        self.write_word(servo_id, REG_MAX_ANGLE, 0)
        
        self.lock_eprom(servo_id, 'sts')
        time.sleep(0.05)
        
        # Set speed (done before enabling torque)
        self.write_word(servo_id, REG_GOAL_SPEED, speed)
        
        # Set acceleration
        self.write_byte(servo_id, REG_ACC, acc)
        
        # Enable torque
        self.write_byte(servo_id, REG_TORQUE_ENABLE, 1)
        time.sleep(0.1)
        
        return True
    
    def disable_step_mode(self, servo_id: int, min_limit: int = 0, max_limit: int = 4095) -> bool:
        """
        Return servo to normal position mode (Mode 0).
        
        Args:
            servo_id: Servo ID
            min_limit: Minimum angle limit (default 0)
            max_limit: Maximum angle limit (default 4095)
            
        Returns:
            True if successful
        """
        self.write_byte(servo_id, REG_TORQUE_ENABLE, 0)
        time.sleep(0.05)
        
        if not self.unlock_eprom(servo_id, 'sts'):
            return False
        
        self.write_byte(servo_id, REG_MODE, 0)
        self.write_word(servo_id, REG_MIN_ANGLE, min_limit)
        self.write_word(servo_id, REG_MAX_ANGLE, max_limit)
        
        self.lock_eprom(servo_id, 'sts')
        time.sleep(0.05)
        
        self.write_byte(servo_id, REG_TORQUE_ENABLE, 1)
        return True
    
    def write_step(self, servo_id: int, steps: int) -> bool:
        """
        Move servo by a number of steps (step mode only).
        
        Args:
            servo_id: Servo ID  
            steps: Number of steps to move (positive or negative)
                   Uses sign-magnitude encoding: bit 15 = direction
                   
        Returns:
            True if successful
            
        Example:
            servo.enable_step_mode(1, speed=300)
            servo.write_step(1, 500)   # Move 500 steps forward
            servo.write_step(1, 500)   # Move 500 more steps forward
            servo.write_step(1, -1000) # Move 1000 steps backward
        """
        # Encode using sign-magnitude (bit 15 = sign)
        encoded = self._to_sign_magnitude(steps, 15)
        
        low, high = self._host2scs(encoded)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_POSITION, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)
    
    def set_step_speed(self, servo_id: int, speed: int) -> bool:
        """
        Set movement speed for step mode.
        
        Args:
            servo_id: Servo ID
            speed: Speed value (typically 50-1000)
            
        Returns:
            True if successful
        """
        low, high = self._host2scs(speed)
        self.serial.reset_input_buffer()
        self._write_buf(servo_id, REG_GOAL_SPEED, bytes([low, high]), Instruction.WRITE)
        return self._ack(servo_id)
    
    # ========================================================================
    # Sync Write (multiple servos at once)
    # ========================================================================
    
    def sync_write_position(self, servos: List[Tuple[int, int, int, int]]):
        """
        Write position to multiple servos simultaneously
        
        Args:
            servos: List of (id, position, time_ms, speed) tuples
        
        Note: For STS/SMS servos, position can be negative (uses sign-magnitude encoding).
              For SCS servos, positions are always unsigned.
        """
        if not servos:
            return
        
        self.serial.reset_input_buffer()
        
        # Build sync write packet
        data_len = 6  # 2 bytes each for position, time, speed
        msg_len = (data_len + 1) * len(servos) + 4
        
        packet = bytes([0xFF, 0xFF, BROADCAST_ID, msg_len, Instruction.SYNC_WRITE,
                       REG_GOAL_POSITION, data_len])
        
        checksum = BROADCAST_ID + msg_len + Instruction.SYNC_WRITE + REG_GOAL_POSITION + data_len
        
        type_class = self.get_type_class()
        memory_map = STS_MEMORY_MAP if type_class.name == 'sts' else SCS_MEMORY_MAP
        reg_info = memory_map.get(REG_GOAL_POSITION)

        for servo_id, position, time_ms, speed in servos:
            if reg_info and reg_info.get('signed_bit') is not None:
                position = self._to_sign_magnitude(position, reg_info['signed_bit'])
            else:
                if position < 0:
                    position = 0x10000 + position
                position = max(0, min(0xFFFF, position))
            
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

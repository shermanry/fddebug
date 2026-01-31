"""
Feetech Servo Protocol Layer

Low-level packet framing, checksum calculation, and UART communication.
Viper-optimized for maximum performance on RP2040.

Protocol Format:
    [0xFF][0xFF][ID][LENGTH][INSTRUCTION][PARAM1]...[PARAMN][CHECKSUM]
    
    LENGTH = number of parameters + 2 (instruction + checksum)
    CHECKSUM = ~(ID + LENGTH + INSTRUCTION + PARAM1 + ... + PARAMN) & 0xFF
"""

import time
from micropython import const

# Instructions
INST_PING = const(0x01)
INST_READ = const(0x02)
INST_WRITE = const(0x03)
INST_REG_WRITE = const(0x04)  # Staged write (waits for ACTION)
INST_ACTION = const(0x05)     # Execute all REG_WRITEs
INST_RESET = const(0x06)
INST_SYNC_WRITE = const(0x83) # Write to multiple servos atomically

# Response status bits
STATUS_VOLTAGE_ERROR = const(0x01)
STATUS_ANGLE_LIMIT_ERROR = const(0x02)
STATUS_OVERHEAT_ERROR = const(0x04)
STATUS_RANGE_ERROR = const(0x08)
STATUS_CHECKSUM_ERROR = const(0x10)
STATUS_OVERLOAD_ERROR = const(0x20)
STATUS_INSTRUCTION_ERROR = const(0x40)

# Broadcast ID (no response expected)
BROADCAST_ID = const(0xFE)

# Timing constants (microseconds)
BYTE_TIME_1M = const(10)  # ~10us per byte at 1Mbaud
RESPONSE_DELAY = const(100)  # Minimum delay before response


class ProtocolError(Exception):
    """Base exception for protocol errors."""
    pass


class TimeoutError(ProtocolError):
    """No response received within timeout."""
    pass


class ChecksumError(ProtocolError):
    """Response checksum validation failed."""
    pass


class StatusError(ProtocolError):
    """Servo returned an error status."""
    def __init__(self, status):
        self.status = status
        super().__init__(f"Servo error: 0x{status:02X}")


# Try to use Viper for performance, fall back to pure Python
try:
    from .viper_math import checksum as _viper_checksum
    
    def calc_checksum(data: bytes) -> int:
        return _viper_checksum(data, len(data))
    
except ImportError:
    # Try local Viper definition
    try:
        import micropython
        
        @micropython.viper
        def _calc_checksum_viper(data, length: int) -> int:
            """Viper-optimized checksum calculation."""
            buf = ptr8(data)
            total: int = 0
            for i in range(length):
                total += buf[i]
            return (~total) & 0xFF
        
        def calc_checksum(data: bytes) -> int:
            return _calc_checksum_viper(data, len(data))
            
    except:
        # Fallback for testing on CPython
        def calc_checksum(data: bytes) -> int:
            """Calculate Feetech packet checksum."""
            return (~sum(data)) & 0xFF


def build_packet(servo_id: int, instruction: int, params: bytes = b'') -> bytes:
    """
    Build a complete command packet.
    
    Args:
        servo_id: Target servo ID (0-253, or 0xFE for broadcast)
        instruction: Command instruction byte
        params: Parameter bytes (can be empty)
    
    Returns:
        Complete packet bytes ready for transmission
    """
    length = len(params) + 2  # instruction + checksum
    header = bytes([0xFF, 0xFF, servo_id, length, instruction])
    checksum_data = bytes([servo_id, length, instruction]) + params
    checksum = calc_checksum(checksum_data)
    return header + params + bytes([checksum])


def build_sync_write_packet(start_reg: int, data_len: int, 
                            servo_data: list) -> bytes:
    """
    Build a SYNC_WRITE packet for multiple servos.
    
    This is the key to achieving high frame rates - one packet updates
    all servos simultaneously.
    
    Args:
        start_reg: Starting register address
        data_len: Number of bytes per servo
        servo_data: List of (servo_id, data_bytes) tuples
    
    Returns:
        Complete sync_write packet
    
    Example:
        # Set position for 3 servos (2 bytes each)
        packet = build_sync_write_packet(
            SMSReg.GOAL_POSITION_L, 2,
            [(1, b'\\x00\\x08'), (2, b'\\x00\\x10'), (3, b'\\x00\\x18')]
        )
    """
    # Sync write format:
    # [0xFF][0xFF][0xFE][LEN][0x83][START_REG][DATA_LEN][ID1][D1]...[IDn][Dn][CHK]
    
    num_servos = len(servo_data)
    total_params = 2 + num_servos * (1 + data_len)  # start_reg, data_len, then id+data per servo
    length = total_params + 2  # +2 for instruction and checksum
    
    # Build parameter section
    params = bytearray([start_reg, data_len])
    for servo_id, data in servo_data:
        params.append(servo_id)
        params.extend(data)
    
    header = bytes([0xFF, 0xFF, BROADCAST_ID, length, INST_SYNC_WRITE])
    checksum_data = bytes([BROADCAST_ID, length, INST_SYNC_WRITE]) + bytes(params)
    checksum = calc_checksum(checksum_data)
    
    return header + bytes(params) + bytes([checksum])


def build_action_packet() -> bytes:
    """
    Build an ACTION packet to trigger all pending REG_WRITEs.
    
    Use REG_WRITE + ACTION for perfectly synchronized motion start
    across multiple servos.
    """
    return build_packet(BROADCAST_ID, INST_ACTION)


class Protocol:
    """
    UART protocol handler with buffered I/O and timeout management.
    
    Designed for high-throughput communication at 1Mbaud with
    proper timing and error handling.
    """
    
    # Pre-allocated buffers for zero-allocation operation
    _tx_buf = bytearray(256)
    _rx_buf = bytearray(256)
    
    def __init__(self, uart, timeout_ms: int = 10, retries: int = 2):
        """
        Initialize protocol handler.
        
        Args:
            uart: MicroPython UART object (already configured)
            timeout_ms: Response timeout in milliseconds
            retries: Number of retry attempts on failure
        """
        self.uart = uart
        self.timeout_ms = timeout_ms
        self.retries = retries
        self._last_tx_time = 0
    
    def send(self, packet: bytes) -> None:
        """
        Send a packet, ensuring proper inter-packet timing.
        """
        # Clear any pending RX data
        while self.uart.any():
            self.uart.read()
        
        self.uart.write(packet)
        self._last_tx_time = time.ticks_us()
    
    def receive(self, expected_params: int = 0) -> tuple:
        """
        Receive and parse a response packet.
        
        Args:
            expected_params: Expected number of parameter bytes
        
        Returns:
            Tuple of (servo_id, error_status, params_bytes)
        
        Raises:
            TimeoutError: No response within timeout
            ChecksumError: Response checksum invalid
            StatusError: Servo returned error status
        """
        # Response format: [0xFF][0xFF][ID][LEN][ERR][PARAMS][CHK]
        # Minimum response is 6 bytes (no params)
        expected_len = 6 + expected_params
        
        deadline = time.ticks_add(time.ticks_ms(), self.timeout_ms)
        received = 0
        
        while received < expected_len:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise TimeoutError(f"Timeout after {received} bytes")
            
            if self.uart.any():
                chunk = self.uart.read(expected_len - received)
                if chunk:
                    for b in chunk:
                        self._rx_buf[received] = b
                        received += 1
            else:
                time.sleep_us(10)
        
        # Validate header
        if self._rx_buf[0] != 0xFF or self._rx_buf[1] != 0xFF:
            raise ProtocolError("Invalid response header")
        
        servo_id = self._rx_buf[2]
        length = self._rx_buf[3]
        error = self._rx_buf[4]
        
        # Validate checksum
        checksum_data = bytes(self._rx_buf[2:5 + expected_params])
        expected_checksum = calc_checksum(checksum_data)
        actual_checksum = self._rx_buf[5 + expected_params]
        
        if expected_checksum != actual_checksum:
            raise ChecksumError(f"Checksum mismatch: {expected_checksum} != {actual_checksum}")
        
        # Check for servo errors
        if error != 0:
            raise StatusError(error)
        
        # Extract parameters
        params = bytes(self._rx_buf[5:5 + expected_params])
        return servo_id, error, params
    
    def ping(self, servo_id: int) -> bool:
        """
        Ping a servo to check if it's responding.
        
        Returns:
            True if servo responded, False otherwise
        """
        packet = build_packet(servo_id, INST_PING)
        
        for attempt in range(self.retries + 1):
            try:
                self.send(packet)
                self.receive(0)
                return True
            except (TimeoutError, ChecksumError):
                if attempt < self.retries:
                    time.sleep_ms(1)
                continue
        
        return False
    
    def read(self, servo_id: int, reg: int, length: int = 1) -> bytes:
        """
        Read registers from a servo.
        
        Args:
            servo_id: Target servo ID
            reg: Starting register address
            length: Number of bytes to read
        
        Returns:
            Bytes read from registers
        """
        packet = build_packet(servo_id, INST_READ, bytes([reg, length]))
        
        for attempt in range(self.retries + 1):
            try:
                self.send(packet)
                _, _, params = self.receive(length)
                return params
            except (TimeoutError, ChecksumError) as e:
                if attempt < self.retries:
                    time.sleep_ms(1)
                    continue
                raise
    
    def write(self, servo_id: int, reg: int, data: bytes) -> None:
        """
        Write registers to a servo.
        
        Args:
            servo_id: Target servo ID
            reg: Starting register address
            data: Bytes to write
        """
        packet = build_packet(servo_id, INST_WRITE, bytes([reg]) + data)
        
        for attempt in range(self.retries + 1):
            try:
                self.send(packet)
                if servo_id != BROADCAST_ID:
                    self.receive(0)
                return
            except (TimeoutError, ChecksumError) as e:
                if attempt < self.retries:
                    time.sleep_ms(1)
                    continue
                raise
    
    def reg_write(self, servo_id: int, reg: int, data: bytes) -> None:
        """
        Staged write - data is buffered until ACTION command.
        
        Use this with action() for synchronized multi-servo commands.
        """
        packet = build_packet(servo_id, INST_REG_WRITE, bytes([reg]) + data)
        self.send(packet)
        if servo_id != BROADCAST_ID:
            self.receive(0)
    
    def action(self) -> None:
        """
        Trigger all pending REG_WRITE commands simultaneously.
        
        This ensures all servos start moving at exactly the same time.
        """
        self.send(build_action_packet())
    
    def sync_write(self, start_reg: int, data_len: int, 
                   servo_data: list) -> None:
        """
        Write to multiple servos in a single packet.
        
        This is the most efficient way to update many servos.
        No response is expected (broadcast).
        
        Args:
            start_reg: Starting register address
            data_len: Number of bytes per servo
            servo_data: List of (servo_id, data_bytes) tuples
        """
        packet = build_sync_write_packet(start_reg, data_len, servo_data)
        self.send(packet)


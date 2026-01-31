"""
Utility Functions

Helper functions for common operations like value conversion,
clamping, and debugging.
"""

import time


def clamp(value, min_val, max_val):
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


def lerp(a, b, t):
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t


def map_range(value, in_min, in_max, out_min, out_max):
    """Map a value from one range to another."""
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def degrees_to_radians(degrees):
    """Convert degrees to radians."""
    import math
    return degrees * math.pi / 180


def radians_to_degrees(radians):
    """Convert radians to degrees."""
    import math
    return radians * 180 / math.pi


class RateLimiter:
    """
    Simple rate limiter for throttling operations.
    
    Usage:
        limiter = RateLimiter(rate_hz=10)
        
        while True:
            if limiter.ready():
                do_something()
    """
    
    def __init__(self, rate_hz: float):
        """
        Initialize rate limiter.
        
        Args:
            rate_hz: Maximum rate in operations per second
        """
        self.interval_ms = int(1000 / rate_hz)
        self._last_time = 0
    
    def ready(self) -> bool:
        """Check if enough time has passed for next operation."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_time) >= self.interval_ms:
            self._last_time = now
            return True
        return False
    
    def wait(self) -> None:
        """Block until next operation time."""
        now = time.ticks_ms()
        remaining = self.interval_ms - time.ticks_diff(now, self._last_time)
        if remaining > 0:
            time.sleep_ms(remaining)
        self._last_time = time.ticks_ms()


class Stopwatch:
    """
    Simple stopwatch for timing operations.
    
    Usage:
        sw = Stopwatch()
        sw.start()
        do_something()
        print(f"Took {sw.elapsed_ms()}ms")
    """
    
    def __init__(self):
        self._start_time = 0
        self._running = False
    
    def start(self) -> None:
        """Start or restart the stopwatch."""
        self._start_time = time.ticks_us()
        self._running = True
    
    def stop(self) -> int:
        """Stop and return elapsed microseconds."""
        if self._running:
            self._running = False
            return time.ticks_diff(time.ticks_us(), self._start_time)
        return 0
    
    def elapsed_us(self) -> int:
        """Get elapsed microseconds (without stopping)."""
        if self._running:
            return time.ticks_diff(time.ticks_us(), self._start_time)
        return 0
    
    def elapsed_ms(self) -> float:
        """Get elapsed milliseconds (without stopping)."""
        return self.elapsed_us() / 1000


class MovingAverage:
    """
    Simple moving average filter.
    
    Useful for smoothing sensor readings.
    """
    
    def __init__(self, window_size: int = 10):
        self._size = window_size
        self._values = []
        self._sum = 0
    
    def add(self, value: float) -> float:
        """Add a value and return the current average."""
        self._values.append(value)
        self._sum += value
        
        if len(self._values) > self._size:
            self._sum -= self._values.pop(0)
        
        return self._sum / len(self._values)
    
    @property
    def value(self) -> float:
        """Get current average."""
        if not self._values:
            return 0
        return self._sum / len(self._values)
    
    def clear(self) -> None:
        """Clear all values."""
        self._values.clear()
        self._sum = 0


def hexdump(data: bytes, prefix: str = "") -> None:
    """
    Print a hex dump of data (for debugging).
    
    Args:
        data: Bytes to dump
        prefix: Optional prefix for each line
    """
    hex_str = " ".join(f"{b:02X}" for b in data)
    print(f"{prefix}{hex_str}")


def format_status(status: dict) -> str:
    """
    Format a servo status dict as a readable string.
    
    Args:
        status: Dict from servo.read_status()
    
    Returns:
        Formatted string
    """
    lines = []
    if 'position' in status:
        lines.append(f"Position: {status['position']} ticks")
    if 'angle' in status:
        lines.append(f"Angle: {status['angle']:.1f}°")
    if 'speed' in status:
        lines.append(f"Speed: {status['speed']}")
    if 'load' in status:
        lines.append(f"Load: {status['load']}")
    if 'voltage' in status:
        lines.append(f"Voltage: {status['voltage']:.1f}V")
    if 'temperature' in status:
        lines.append(f"Temperature: {status['temperature']}°C")
    return "\n".join(lines)


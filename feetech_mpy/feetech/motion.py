"""
Motion Planning and Trajectory Generation

Provides smooth motion profiles with configurable jerk for
professional-quality servo animations.

Key concepts:
- Jerk: Rate of change of acceleration (smoothness control)
- S-curve: 7-phase motion profile with smooth acceleration transitions
- Trapezoidal: 3-phase motion profile (simpler, faster computation)

For 30+ FPS animation with 16 servos, we use pre-computed profiles
and interpolate at runtime.

Performance: Uses Viper-optimized fixed-point math when available
for maximum performance on RP2040.
"""

import math
import time

# Import Viper-optimized math (with fallbacks)
try:
    from .viper_math import (
        interpolate_position,
        position_at_time_fp,
        smoothstep5,
        FP_ONE,
    )
    _USE_VIPER = True
except ImportError:
    _USE_VIPER = False


class MotionProfile:
    """
    Base class for motion profiles.
    
    A motion profile defines how a servo moves from start to end position
    over time, specifying position, velocity, and acceleration at each
    point along the trajectory.
    """
    
    def __init__(self, start_pos: int, end_pos: int, duration_ms: int):
        """
        Initialize motion profile.
        
        Args:
            start_pos: Starting position (ticks)
            end_pos: Target position (ticks)
            duration_ms: Total motion duration (milliseconds)
        """
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.duration_ms = duration_ms
        self.distance = end_pos - start_pos
        self._start_time = 0
    
    def start(self) -> None:
        """Mark the motion as started (records start time)."""
        self._start_time = time.ticks_ms()
    
    def elapsed_ms(self) -> int:
        """Get elapsed time since motion started."""
        return time.ticks_diff(time.ticks_ms(), self._start_time)
    
    def progress(self) -> float:
        """
        Get motion progress as fraction [0.0, 1.0].
        
        Returns 1.0 if motion is complete.
        """
        if self.duration_ms <= 0:
            return 1.0
        t = self.elapsed_ms() / self.duration_ms
        return min(1.0, max(0.0, t))
    
    def is_complete(self) -> bool:
        """Check if motion has completed."""
        return self.elapsed_ms() >= self.duration_ms
    
    def position_at(self, t: float) -> int:
        """
        Get position at normalized time t.
        
        Args:
            t: Normalized time [0.0, 1.0]
        
        Returns:
            Position in ticks
        
        Override in subclasses to implement specific profiles.
        """
        # Default: linear interpolation
        return int(self.start_pos + self.distance * t)
    
    def current_position(self) -> int:
        """Get current target position based on elapsed time."""
        return self.position_at(self.progress())
    
    def velocity_at(self, t: float) -> float:
        """
        Get velocity at normalized time t.
        
        Args:
            t: Normalized time [0.0, 1.0]
        
        Returns:
            Velocity in ticks/second
        
        Override in subclasses for accurate velocity.
        """
        # Default: constant velocity
        if self.duration_ms <= 0:
            return 0
        return (self.distance / self.duration_ms) * 1000


class LinearProfile(MotionProfile):
    """
    Simple linear interpolation.
    
    Constant velocity, instant acceleration at start/end.
    Fast to compute but jerky motion.
    """
    
    def position_at(self, t: float) -> int:
        return int(self.start_pos + self.distance * t)


class TrapezoidalProfile(MotionProfile):
    """
    Trapezoidal velocity profile.
    
    Three phases:
    1. Acceleration (ramp up)
    2. Cruise (constant velocity)
    3. Deceleration (ramp down)
    
    Smoother than linear but still has abrupt jerk.
    """
    
    def __init__(self, start_pos: int, end_pos: int, duration_ms: int,
                 accel_fraction: float = 0.25):
        """
        Initialize trapezoidal profile.
        
        Args:
            start_pos: Starting position
            end_pos: Target position
            duration_ms: Total duration
            accel_fraction: Fraction of time spent accelerating (0.1-0.5)
        """
        super().__init__(start_pos, end_pos, duration_ms)
        self.accel_fraction = min(0.5, max(0.1, accel_fraction))
        self.decel_fraction = self.accel_fraction
        self.cruise_fraction = 1.0 - 2 * self.accel_fraction
    
    def position_at(self, t: float) -> int:
        t = max(0.0, min(1.0, t))
        
        t1 = self.accel_fraction  # End of acceleration
        t2 = 1.0 - self.decel_fraction  # Start of deceleration
        
        if t <= t1:
            # Acceleration phase: quadratic
            # p = 0.5 * a * t^2, normalized
            phase_t = t / t1
            pos_frac = 0.5 * (t1 / (t1 + self.cruise_fraction + t1)) * (phase_t ** 2)
        elif t <= t2:
            # Cruise phase: linear
            accel_dist = 0.5 * self.accel_fraction
            cruise_t = (t - t1) / self.cruise_fraction
            pos_frac = accel_dist + self.cruise_fraction * cruise_t
        else:
            # Deceleration phase: inverted quadratic
            phase_t = (t - t2) / self.decel_fraction
            # Position = 1 - 0.5 * decel_frac * (1 - phase_t)^2
            remaining = 1.0 - phase_t
            pos_frac = 1.0 - 0.5 * self.decel_fraction * (remaining ** 2)
        
        return int(self.start_pos + self.distance * pos_frac)


class SCurveProfile(MotionProfile):
    """
    S-curve (7-phase) motion profile with jerk control.
    
    Seven phases:
    1. Increasing acceleration (jerk > 0)
    2. Constant acceleration (jerk = 0)
    3. Decreasing acceleration (jerk < 0)
    4. Cruise (acceleration = 0)
    5. Increasing deceleration (jerk < 0)
    6. Constant deceleration (jerk = 0)
    7. Decreasing deceleration (jerk > 0)
    
    The jerk parameter controls how smooth the motion is.
    Lower jerk = smoother but slower response.
    Higher jerk = faster response but more mechanical stress.
    
    This is the preferred profile for animation quality.
    """
    
    def __init__(self, start_pos: int, end_pos: int, duration_ms: int,
                 jerk: float = 1.0, max_accel_fraction: float = 0.3):
        """
        Initialize S-curve profile.
        
        Args:
            start_pos: Starting position
            end_pos: Target position
            duration_ms: Total duration
            jerk: Jerk factor (0.1-10.0). Lower = smoother, higher = snappier
            max_accel_fraction: Maximum fraction of time at peak acceleration
        """
        super().__init__(start_pos, end_pos, duration_ms)
        
        # Jerk controls the shape of the S-curve
        # Higher jerk = sharper transitions (closer to trapezoidal)
        # Lower jerk = smoother transitions (more S-like)
        self.jerk = max(0.1, min(10.0, jerk))
        
        # Pre-compute for fixed-point Viper path
        if _USE_VIPER:
            self._jerk_fp = int(self.jerk * FP_ONE)
        
        # Pre-compute normalized S-curve parameters
        # Using a sigmoid-like function for smooth interpolation
        self._steepness = self.jerk * 4.0  # Map jerk to sigmoid steepness
    
    def _sigmoid(self, x: float) -> float:
        """
        Compute smoothstep-like sigmoid function.
        
        Uses polynomial approximation for speed on microcontroller.
        """
        # Use Viper-optimized version if available
        if _USE_VIPER:
            return smoothstep5(x)
        
        # Clamp to [0, 1]
        x = max(0.0, min(1.0, x))
        
        # Higher order smoothstep for S-curve: 6x^5 - 15x^4 + 10x^3
        # This has zero velocity and acceleration at endpoints
        x3 = x * x * x
        x4 = x3 * x
        x5 = x4 * x
        return 6 * x5 - 15 * x4 + 10 * x3
    
    def _jerk_adjusted_sigmoid(self, t: float) -> float:
        """
        Jerk-adjusted interpolation.
        
        Blends between pure smoothstep and linear based on jerk.
        """
        smooth = self._sigmoid(t)
        
        # High jerk = more linear (snappier)
        # Low jerk = more smoothstep (smoother)
        linear_weight = min(1.0, (self.jerk - 1.0) / 9.0)  # 0 at jerk=1, 1 at jerk=10
        
        return smooth * (1.0 - linear_weight) + t * linear_weight
    
    def position_at(self, t: float) -> int:
        """
        Get position at normalized time t.
        
        Uses Viper-optimized fixed-point math when available.
        """
        # Fast path: use Viper-optimized function
        if _USE_VIPER:
            return interpolate_position(self.start_pos, self.end_pos, t, self.jerk)
        
        # Fallback: pure Python
        t = max(0.0, min(1.0, t))
        pos_frac = self._jerk_adjusted_sigmoid(t)
        return int(self.start_pos + self.distance * pos_frac)
    
    def velocity_at(self, t: float) -> float:
        """
        Get velocity at normalized time.
        
        Derivative of the smoothstep function.
        """
        if self.duration_ms <= 0:
            return 0
        
        t = max(0.0, min(1.0, t))
        
        # Derivative of 6x^5 - 15x^4 + 10x^3 is 30x^4 - 60x^3 + 30x^2
        # = 30x^2(x-1)^2
        x2 = t * t
        deriv = 30 * x2 * (t - 1) * (t - 1)
        
        # Scale to actual velocity
        return deriv * (self.distance / self.duration_ms) * 1000


class MotionQueue:
    """
    Queue of motion segments for continuous animation.
    
    Allows chaining multiple motions together smoothly,
    enabling complex animation sequences.
    """
    
    def __init__(self, max_size: int = 32):
        """
        Initialize motion queue.
        
        Args:
            max_size: Maximum number of queued motions
        """
        self._queue = []
        self._max_size = max_size
        self._current = None
    
    def add(self, profile: MotionProfile) -> bool:
        """
        Add a motion to the queue.
        
        Args:
            profile: Motion profile to add
        
        Returns:
            True if added, False if queue is full
        """
        if len(self._queue) >= self._max_size:
            return False
        self._queue.append(profile)
        return True
    
    def clear(self) -> None:
        """Clear all queued motions."""
        self._queue.clear()
        self._current = None
    
    @property
    def size(self) -> int:
        """Number of motions in queue (including current)."""
        return len(self._queue) + (1 if self._current else 0)
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty and no motion is active."""
        return self._current is None and len(self._queue) == 0
    
    def update(self) -> int:
        """
        Update motion queue and get current position.
        
        Call this at your frame rate (e.g., 30 FPS).
        
        Returns:
            Current target position, or None if queue is empty
        """
        # Check if current motion is complete
        if self._current is not None:
            if self._current.is_complete():
                # Motion finished, get final position
                final_pos = self._current.end_pos
                self._current = None
                
                # Start next motion if available
                if self._queue:
                    self._current = self._queue.pop(0)
                    self._current.start()
                
                return final_pos
            else:
                return self._current.current_position()
        
        # No current motion, try to start next
        if self._queue:
            self._current = self._queue.pop(0)
            self._current.start()
            return self._current.current_position()
        
        return None
    
    @property
    def is_moving(self) -> bool:
        """Check if a motion is currently active."""
        return self._current is not None and not self._current.is_complete()


def create_scurve_move(start: int, end: int, duration_ms: int,
                       jerk: float = 1.0) -> SCurveProfile:
    """
    Convenience function to create an S-curve motion.
    
    Args:
        start: Starting position (ticks)
        end: Target position (ticks)
        duration_ms: Motion duration (milliseconds)
        jerk: Jerk factor (0.1-10.0). Default 1.0 is balanced.
              - 0.1-0.5: Very smooth, slow response (gentle animation)
              - 0.5-2.0: Balanced (good for most animation)
              - 2.0-5.0: Snappy, quick response (dynamic motion)
              - 5.0-10.0: Very snappy (near-trapezoidal)
    
    Returns:
        Configured SCurveProfile ready for use
    """
    return SCurveProfile(start, end, duration_ms, jerk=jerk)


def interpolate_positions(positions: list, total_duration_ms: int,
                          jerk: float = 1.0) -> list:
    """
    Create a sequence of S-curve motions through waypoints.
    
    Args:
        positions: List of positions to move through
        total_duration_ms: Total time for entire sequence
        jerk: Jerk factor for all segments
    
    Returns:
        List of MotionProfile objects for the sequence
    """
    if len(positions) < 2:
        return []
    
    num_segments = len(positions) - 1
    segment_duration = total_duration_ms // num_segments
    
    profiles = []
    for i in range(num_segments):
        profile = SCurveProfile(
            positions[i],
            positions[i + 1],
            segment_duration,
            jerk=jerk
        )
        profiles.append(profile)
    
    return profiles


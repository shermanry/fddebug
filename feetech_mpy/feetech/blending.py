"""
Motion Blending and Spline Interpolation

Provides smooth motion transitions when interrupting ongoing animations.
Uses Hermite splines for velocity-continuous blending.

Key concepts:
- Velocity continuity: New motion starts with current velocity
- Hermite splines: Define motion by position + velocity at endpoints
- Blend time: How quickly to transition to new trajectory

Usage:
    # During animation, interrupt with new target
    scheduler.interrupt(servo_id, new_position, duration_ms, jerk)
    
    # Or for all servos
    scheduler.interrupt_all(new_positions, duration_ms, jerk)
"""

import math
import time

# Import Viper-optimized math (with fallbacks)
try:
    from .viper_math import (
        hermite_eval_fp,
        smoothstep5,
        FP_ONE,
        float_to_fp,
        fp_to_float,
    )
    _USE_VIPER = True
except ImportError:
    _USE_VIPER = False
    FP_ONE = 65536
    def float_to_fp(f): return int(f * FP_ONE)
    def fp_to_float(fp): return fp / FP_ONE


class HermiteSpline:
    """
    Cubic Hermite spline interpolation.
    
    Interpolates between two points with specified velocities at each endpoint.
    This ensures velocity continuity when blending motions.
    
    The curve is defined by:
    - p0: Start position
    - v0: Start velocity (per normalized time unit)
    - p1: End position  
    - v1: End velocity (per normalized time unit)
    
    Uses Viper-optimized fixed-point math when available for maximum
    performance on RP2040.
    """
    
    def __init__(self, p0: float, v0: float, p1: float, v1: float):
        """
        Initialize Hermite spline.
        
        Args:
            p0: Start position
            v0: Start velocity (scaled to duration)
            p1: End position
            v1: End velocity (scaled to duration)
        """
        self.p0 = p0
        self.v0 = v0
        self.p1 = p1
        self.v1 = v1
        
        # Pre-compute Hermite basis coefficients (float)
        # h(t) = at³ + bt² + ct + d
        self._a = 2 * p0 - 2 * p1 + v0 + v1
        self._b = -3 * p0 + 3 * p1 - 2 * v0 - v1
        self._c = v0
        self._d = p0
        
        # Pre-compute fixed-point coefficients for Viper path
        if _USE_VIPER:
            self._a_fp = float_to_fp(self._a)
            self._b_fp = float_to_fp(self._b)
            self._c_fp = float_to_fp(self._c)
            self._d_fp = float_to_fp(self._d)
    
    def position(self, t: float) -> float:
        """
        Get position at normalized time t [0, 1].
        
        Uses Viper-optimized fixed-point when available.
        """
        # Fast path: Viper fixed-point
        if _USE_VIPER:
            t_fp = int(max(0.0, min(1.0, t)) * FP_ONE)
            result_fp = hermite_eval_fp(
                self._a_fp, self._b_fp, self._c_fp, self._d_fp, t_fp
            )
            return fp_to_float(result_fp)
        
        # Fallback: pure Python
        t = max(0.0, min(1.0, t))
        t2 = t * t
        t3 = t2 * t
        return self._a * t3 + self._b * t2 + self._c * t + self._d
    
    def velocity(self, t: float) -> float:
        """
        Get velocity at normalized time t [0, 1].
        
        Derivative of position: 3at² + 2bt + c
        """
        t = max(0.0, min(1.0, t))
        return 3 * self._a * t * t + 2 * self._b * t + self._c
    
    def acceleration(self, t: float) -> float:
        """
        Get acceleration at normalized time t [0, 1].
        
        Second derivative: 6at + 2b
        """
        t = max(0.0, min(1.0, t))
        return 6 * self._a * t + 2 * self._b


class BlendableProfile:
    """
    Motion profile that supports smooth blending from interrupted motion.
    
    Uses Hermite splines to ensure velocity continuity when transitioning
    from one motion to another.
    """
    
    def __init__(self, start_pos: int, start_vel: float,
                 end_pos: int, end_vel: float,
                 duration_ms: int, jerk: float = 1.0):
        """
        Initialize blendable motion profile.
        
        Args:
            start_pos: Starting position (ticks)
            start_vel: Starting velocity (ticks per second)
            end_pos: Target position (ticks)
            end_vel: Target velocity at end (usually 0 for stopping)
            duration_ms: Motion duration (milliseconds)
            jerk: Jerk factor affecting velocity profile shape
        """
        self.start_pos = start_pos
        self.start_vel = start_vel
        self.end_pos = end_pos
        self.end_vel = end_vel
        self.duration_ms = duration_ms
        self.jerk = max(0.1, min(10.0, jerk))
        
        # Scale velocities to normalized time [0, 1]
        # v_normalized = v_real * duration_ms / 1000
        duration_sec = duration_ms / 1000.0
        v0_scaled = start_vel * duration_sec
        v1_scaled = end_vel * duration_sec
        
        # Create Hermite spline
        self._spline = HermiteSpline(
            float(start_pos), v0_scaled,
            float(end_pos), v1_scaled
        )
        
        self._start_time = 0
        self._duration_sec = duration_sec
    
    def start(self) -> None:
        """Mark motion as started."""
        self._start_time = time.ticks_ms()
    
    def elapsed_ms(self) -> int:
        """Get elapsed time since start."""
        return time.ticks_diff(time.ticks_ms(), self._start_time)
    
    def progress(self) -> float:
        """Get progress as fraction [0, 1]."""
        if self.duration_ms <= 0:
            return 1.0
        t = self.elapsed_ms() / self.duration_ms
        return min(1.0, max(0.0, t))
    
    def is_complete(self) -> bool:
        """Check if motion is complete."""
        return self.elapsed_ms() >= self.duration_ms
    
    def position_at(self, t: float) -> int:
        """Get position at normalized time t."""
        # Apply jerk-based time warping for S-curve feel
        t_warped = self._apply_jerk(t)
        return int(self._spline.position(t_warped))
    
    def velocity_at(self, t: float) -> float:
        """
        Get velocity at normalized time t (ticks per second).
        """
        t_warped = self._apply_jerk(t)
        # Spline velocity is per normalized time, convert to per second
        v_normalized = self._spline.velocity(t_warped)
        return v_normalized / self._duration_sec if self._duration_sec > 0 else 0
    
    def current_position(self) -> int:
        """Get current target position."""
        return self.position_at(self.progress())
    
    def current_velocity(self) -> float:
        """Get current velocity (ticks per second)."""
        return self.velocity_at(self.progress())
    
    def _apply_jerk(self, t: float) -> float:
        """
        Apply jerk-based time warping.
        
        Higher jerk = more linear (snappy)
        Lower jerk = more S-curve (smooth)
        """
        t = max(0.0, min(1.0, t))
        
        # Smoothstep for low jerk
        x3 = t * t * t
        x4 = x3 * t
        x5 = x4 * t
        smooth = 6 * x5 - 15 * x4 + 10 * x3
        
        # Blend between smooth and linear based on jerk
        linear_weight = min(1.0, (self.jerk - 1.0) / 9.0)
        return smooth * (1.0 - linear_weight) + t * linear_weight


class MotionState:
    """
    Tracks the current motion state for a servo, enabling smooth interrupts.
    
    Maintains position and velocity estimates even between explicit reads.
    """
    
    def __init__(self):
        self.position: float = 0.0
        self.velocity: float = 0.0
        self.last_update: int = 0
        self._profile: BlendableProfile = None
    
    def update_from_profile(self, profile: BlendableProfile) -> None:
        """Update state from active motion profile."""
        if profile is not None and not profile.is_complete():
            self.position = profile.current_position()
            self.velocity = profile.current_velocity()
            self.last_update = time.ticks_ms()
            self._profile = profile
    
    def update_from_reading(self, position: int) -> None:
        """
        Update state from actual servo reading.
        
        Estimates velocity from position change.
        """
        now = time.ticks_ms()
        if self.last_update > 0:
            dt = time.ticks_diff(now, self.last_update) / 1000.0
            if dt > 0:
                self.velocity = (position - self.position) / dt
        
        self.position = float(position)
        self.last_update = now
    
    def extrapolate(self) -> tuple:
        """
        Extrapolate current position and velocity.
        
        Returns:
            (position, velocity) tuple
        """
        # If we have an active profile, use it
        if self._profile is not None and not self._profile.is_complete():
            return (self._profile.current_position(), 
                    self._profile.current_velocity())
        
        # Otherwise extrapolate from last known state
        now = time.ticks_ms()
        dt = time.ticks_diff(now, self.last_update) / 1000.0
        
        # Simple linear extrapolation with velocity decay
        decay = max(0, 1.0 - dt * 2)  # Velocity decays over 0.5s
        current_vel = self.velocity * decay
        current_pos = self.position + self.velocity * dt * 0.5  # Average velocity
        
        return (int(current_pos), current_vel)


def create_blend_profile(current_pos: int, current_vel: float,
                         target_pos: int, duration_ms: int,
                         jerk: float = 1.0,
                         target_vel: float = 0.0) -> BlendableProfile:
    """
    Create a motion profile that blends smoothly from current state.
    
    Args:
        current_pos: Current position (ticks)
        current_vel: Current velocity (ticks/second)
        target_pos: Target position (ticks)
        duration_ms: Motion duration (milliseconds)
        jerk: Jerk factor (0.1-10.0)
        target_vel: Target velocity at end (usually 0)
    
    Returns:
        BlendableProfile ready to start
    """
    return BlendableProfile(
        current_pos, current_vel,
        target_pos, target_vel,
        duration_ms, jerk
    )


class CatmullRomSpline:
    """
    Catmull-Rom spline for smooth multi-point interpolation.
    
    Given a sequence of control points, creates a smooth curve
    that passes through all points with continuous velocity.
    
    Great for keyframe animation with automatic velocity calculation.
    """
    
    def __init__(self, points: list, tension: float = 0.5):
        """
        Initialize Catmull-Rom spline.
        
        Args:
            points: List of (time_ms, position) tuples
            tension: Curve tension (0=loose, 1=tight)
        """
        self.points = sorted(points, key=lambda p: p[0])
        self.tension = tension
        
        if len(self.points) < 2:
            raise ValueError("Need at least 2 points")
    
    @property
    def duration(self) -> int:
        """Total duration in milliseconds."""
        return self.points[-1][0] - self.points[0][0]
    
    def position_at_time(self, time_ms: int) -> float:
        """
        Get position at absolute time.
        
        Args:
            time_ms: Time in milliseconds from start
        
        Returns:
            Interpolated position
        """
        # Find the segment containing this time
        t = time_ms + self.points[0][0]
        
        # Clamp to valid range
        if t <= self.points[0][0]:
            return self.points[0][1]
        if t >= self.points[-1][0]:
            return self.points[-1][1]
        
        # Find segment
        for i in range(len(self.points) - 1):
            t0, p0 = self.points[i]
            t1, p1 = self.points[i + 1]
            
            if t0 <= t <= t1:
                # Get surrounding points for Catmull-Rom
                pm1 = self.points[max(0, i - 1)][1]
                p2 = self.points[min(len(self.points) - 1, i + 2)][1]
                
                # Normalize t to [0, 1] within segment
                u = (t - t0) / (t1 - t0) if t1 > t0 else 0
                
                return self._catmull_rom(pm1, p0, p1, p2, u)
        
        return self.points[-1][1]
    
    def _catmull_rom(self, p0: float, p1: float, p2: float, p3: float, 
                     t: float) -> float:
        """
        Catmull-Rom interpolation between p1 and p2.
        
        p0 and p3 are used to calculate tangents.
        """
        t2 = t * t
        t3 = t2 * t
        
        # Catmull-Rom basis functions with tension
        s = (1 - self.tension) / 2
        
        return (
            (-s * t3 + 2 * s * t2 - s * t) * p0 +
            ((2 - s) * t3 + (s - 3) * t2 + 1) * p1 +
            ((s - 2) * t3 + (3 - 2 * s) * t2 + s * t) * p2 +
            (s * t3 - s * t2) * p3
        )


class SplineAnimation:
    """
    Multi-servo spline-based animation.
    
    Uses Catmull-Rom splines for smooth multi-point animation
    with automatic velocity calculation.
    """
    
    def __init__(self):
        self._splines = {}  # servo_id -> CatmullRomSpline
        self._start_time = 0
        self._duration = 0
    
    def add_keyframes(self, servo_id: int, keyframes: list) -> None:
        """
        Add keyframes for a servo.
        
        Args:
            servo_id: Servo ID
            keyframes: List of (time_ms, position) tuples
        """
        if len(keyframes) >= 2:
            self._splines[servo_id] = CatmullRomSpline(keyframes)
            self._duration = max(self._duration, 
                                self._splines[servo_id].duration)
    
    def start(self) -> None:
        """Start the animation."""
        self._start_time = time.ticks_ms()
    
    def elapsed_ms(self) -> int:
        """Get elapsed time."""
        return time.ticks_diff(time.ticks_ms(), self._start_time)
    
    def is_complete(self) -> bool:
        """Check if animation is complete."""
        return self.elapsed_ms() >= self._duration
    
    def get_positions(self) -> dict:
        """
        Get current target positions for all servos.
        
        Returns:
            Dict of {servo_id: position}
        """
        t = self.elapsed_ms()
        positions = {}
        
        for servo_id, spline in self._splines.items():
            positions[servo_id] = int(spline.position_at_time(t))
        
        return positions
    
    @property
    def servo_ids(self) -> list:
        """List of servo IDs in animation."""
        return list(self._splines.keys())


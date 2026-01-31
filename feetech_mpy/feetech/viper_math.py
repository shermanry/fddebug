"""
Viper-Optimized Math Functions

High-performance implementations of critical math operations
using MicroPython's Viper native code emitter.

These functions are called at every frame for every servo,
so even small optimizations have significant impact at 30+ FPS
with 16 servos.

Performance targets:
- Smoothstep: < 5µs
- Hermite eval: < 10µs  
- Pack/unpack: < 2µs
- Checksum: < 1µs per byte

All functions have pure Python fallbacks for CPython testing.
"""

# Try to import micropython for Viper decorators
# Fall back to no-op decorator for CPython
try:
    import micropython
    _HAS_VIPER = True
except ImportError:
    _HAS_VIPER = False
    # Create dummy decorator
    class micropython:
        @staticmethod
        def viper(f):
            return f
        @staticmethod
        def native(f):
            return f


# ============================================================
# FIXED-POINT MATH (avoids float on hot paths)
# ============================================================

# Fixed-point scale: 16 bits fractional
# This gives us 1/65536 precision while staying in 32-bit int
FP_SHIFT = 16
FP_ONE = 1 << FP_SHIFT  # 65536
FP_HALF = 1 << (FP_SHIFT - 1)  # 32768


if _HAS_VIPER:
    @micropython.viper
    def fp_mul(a: int, b: int) -> int:
        """Fixed-point multiply: (a * b) >> 16"""
        # Use 64-bit intermediate to avoid overflow
        result: int = (a * b) >> 16
        return result
    
    @micropython.viper
    def fp_div(a: int, b: int) -> int:
        """Fixed-point divide: (a << 16) / b"""
        if b == 0:
            return 0
        result: int = (a << 16) // b
        return result
else:
    def fp_mul(a: int, b: int) -> int:
        return (a * b) >> FP_SHIFT
    
    def fp_div(a: int, b: int) -> int:
        if b == 0:
            return 0
        return (a << FP_SHIFT) // b


def float_to_fp(f: float) -> int:
    """Convert float to fixed-point."""
    return int(f * FP_ONE)


def fp_to_float(fp: int) -> float:
    """Convert fixed-point to float."""
    return fp / FP_ONE


# ============================================================
# INTERPOLATION FUNCTIONS
# ============================================================

if _HAS_VIPER:
    @micropython.viper
    def smoothstep5_fp(t_fp: int) -> int:
        """
        5th-order smoothstep in fixed-point.
        
        f(t) = 6t^5 - 15t^4 + 10t^3
        
        This has zero velocity and acceleration at t=0 and t=1.
        
        Args:
            t_fp: Normalized time [0, FP_ONE] in fixed-point
        
        Returns:
            Interpolated value [0, FP_ONE] in fixed-point
        """
        # Clamp to [0, FP_ONE]
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        # Calculate powers using fixed-point multiply
        # t is in [0, 65536], we need t^2, t^3, t^4, t^5
        # Each multiply and shift to stay in range
        
        t2: int = (t * t) >> 16
        t3: int = (t2 * t) >> 16
        t4: int = (t3 * t) >> 16
        t5: int = (t4 * t) >> 16
        
        # 6*t5 - 15*t4 + 10*t3
        result: int = 6 * t5 - 15 * t4 + 10 * t3
        
        return result
    
    @micropython.viper
    def lerp_fp(a: int, b: int, t_fp: int) -> int:
        """
        Linear interpolation in fixed-point.
        
        result = a + (b - a) * t
        
        Args:
            a: Start value (regular int)
            b: End value (regular int)
            t_fp: Interpolation factor [0, FP_ONE]
        
        Returns:
            Interpolated value (regular int)
        """
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        delta: int = b - a
        result: int = a + ((delta * t) >> 16)
        return result
    
    @micropython.viper
    def hermite_eval_fp(a: int, b: int, c: int, d: int, t_fp: int) -> int:
        """
        Evaluate cubic polynomial at^3 + bt^2 + ct + d.
        
        Used for Hermite spline evaluation.
        Coefficients a,b,c,d are fixed-point.
        
        Args:
            a, b, c, d: Polynomial coefficients (fixed-point)
            t_fp: Normalized time [0, FP_ONE]
        
        Returns:
            Result in fixed-point
        """
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        t2: int = (t * t) >> 16
        t3: int = (t2 * t) >> 16
        
        # Horner's method: d + t*(c + t*(b + t*a))
        result: int = d + ((t * (c + ((t * (b + ((t * a) >> 16))) >> 16))) >> 16)
        
        return result

else:
    # Pure Python fallbacks
    def smoothstep5_fp(t_fp: int) -> int:
        t = max(0, min(FP_ONE, t_fp)) / FP_ONE
        t3 = t * t * t
        t4 = t3 * t
        t5 = t4 * t
        result = 6 * t5 - 15 * t4 + 10 * t3
        return int(result * FP_ONE)
    
    def lerp_fp(a: int, b: int, t_fp: int) -> int:
        t = max(0, min(FP_ONE, t_fp)) / FP_ONE
        return int(a + (b - a) * t)
    
    def hermite_eval_fp(a: int, b: int, c: int, d: int, t_fp: int) -> int:
        t = max(0, min(FP_ONE, t_fp)) / FP_ONE
        t2 = t * t
        t3 = t2 * t
        result = a * t3 + b * t2 + c * t + d
        return int(result)


# Float versions for convenience
def smoothstep5(t: float) -> float:
    """5th-order smoothstep: 6t^5 - 15t^4 + 10t^3"""
    t = max(0.0, min(1.0, t))
    t3 = t * t * t
    t4 = t3 * t
    t5 = t4 * t
    return 6 * t5 - 15 * t4 + 10 * t3


def smoothstep3(t: float) -> float:
    """3rd-order smoothstep: 3t^2 - 2t^3"""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ============================================================
# BYTE OPERATIONS
# ============================================================

if _HAS_VIPER:
    @micropython.viper
    def pack_word_le(value: int) -> int:
        """
        Pack 16-bit little-endian into two bytes.
        
        Returns packed as: (low_byte << 8) | high_byte
        So caller can do: buf[0] = result >> 8; buf[1] = result & 0xFF
        
        Actually returns (byte0, byte1) packed into int.
        """
        v: int = value & 0xFFFF
        return (v & 0xFF) | ((v >> 8) << 8)
    
    @micropython.viper
    def pack_word_be(value: int) -> int:
        """Pack 16-bit big-endian."""
        v: int = value & 0xFFFF
        return (v >> 8) | ((v & 0xFF) << 8)
    
    @micropython.viper
    def unpack_word_le(b0: int, b1: int) -> int:
        """Unpack 16-bit little-endian from two bytes."""
        return (b0 & 0xFF) | ((b1 & 0xFF) << 8)
    
    @micropython.viper
    def unpack_word_be(b0: int, b1: int) -> int:
        """Unpack 16-bit big-endian from two bytes."""
        return ((b0 & 0xFF) << 8) | (b1 & 0xFF)
    
    @micropython.viper
    def checksum(data, length: int) -> int:
        """
        Calculate Feetech checksum.
        
        checksum = (~sum(bytes)) & 0xFF
        """
        buf = ptr8(data)
        total: int = 0
        for i in range(length):
            total += buf[i]
        return (~total) & 0xFF

else:
    def pack_word_le(value: int) -> int:
        v = value & 0xFFFF
        return (v & 0xFF) | ((v >> 8) << 8)
    
    def pack_word_be(value: int) -> int:
        v = value & 0xFFFF
        return (v >> 8) | ((v & 0xFF) << 8)
    
    def unpack_word_le(b0: int, b1: int) -> int:
        return (b0 & 0xFF) | ((b1 & 0xFF) << 8)
    
    def unpack_word_be(b0: int, b1: int) -> int:
        return ((b0 & 0xFF) << 8) | (b1 & 0xFF)
    
    def checksum(data, length: int) -> int:
        return (~sum(data[:length])) & 0xFF


# ============================================================
# MOTION PROFILE HELPERS
# ============================================================

if _HAS_VIPER:
    @micropython.viper
    def blend_jerk_fp(t_fp: int, jerk_fp: int) -> int:
        """
        Apply jerk-based blending between smoothstep and linear.
        
        Higher jerk = more linear (snappier)
        Lower jerk = more smoothstep (smoother)
        
        Args:
            t_fp: Normalized time [0, FP_ONE]
            jerk_fp: Jerk factor [0, 10*FP_ONE]
        
        Returns:
            Blended interpolation factor [0, FP_ONE]
        """
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        # Calculate smoothstep
        t2: int = (t * t) >> 16
        t3: int = (t2 * t) >> 16
        t4: int = (t3 * t) >> 16
        t5: int = (t4 * t) >> 16
        smooth: int = 6 * t5 - 15 * t4 + 10 * t3
        
        # Calculate linear weight from jerk
        # jerk 1.0 (65536) -> weight 0
        # jerk 10.0 (655360) -> weight 1.0 (65536)
        jerk: int = jerk_fp
        linear_weight: int = (jerk - 65536) * 65536 // (9 * 65536)
        if linear_weight < 0:
            linear_weight = 0
        elif linear_weight > 65536:
            linear_weight = 65536
        
        # Blend: smooth * (1 - weight) + linear * weight
        smooth_weight: int = 65536 - linear_weight
        result: int = ((smooth * smooth_weight) >> 16) + ((t * linear_weight) >> 16)
        
        return result
    
    @micropython.viper
    def position_at_time_fp(start: int, distance: int, 
                            t_fp: int, jerk_fp: int) -> int:
        """
        Calculate position at normalized time with S-curve.
        
        Args:
            start: Start position (regular int)
            distance: End - start (regular int)
            t_fp: Normalized time [0, FP_ONE]
            jerk_fp: Jerk factor (fixed-point)
        
        Returns:
            Current position (regular int)
        """
        # Get blended interpolation factor
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        # Smoothstep
        t2: int = (t * t) >> 16
        t3: int = (t2 * t) >> 16
        t4: int = (t3 * t) >> 16
        t5: int = (t4 * t) >> 16
        smooth: int = 6 * t5 - 15 * t4 + 10 * t3
        
        # Jerk blending
        jerk: int = jerk_fp
        linear_weight: int = (jerk - 65536) * 65536 // (9 * 65536)
        if linear_weight < 0:
            linear_weight = 0
        elif linear_weight > 65536:
            linear_weight = 65536
        
        smooth_weight: int = 65536 - linear_weight
        interp: int = ((smooth * smooth_weight) >> 16) + ((t * linear_weight) >> 16)
        
        # Calculate position
        pos: int = start + ((distance * interp) >> 16)
        return pos

else:
    def blend_jerk_fp(t_fp: int, jerk_fp: int) -> int:
        t = max(0.0, min(1.0, t_fp / FP_ONE))
        jerk = jerk_fp / FP_ONE
        
        # Smoothstep
        t3 = t * t * t
        t4 = t3 * t
        t5 = t4 * t
        smooth = 6 * t5 - 15 * t4 + 10 * t3
        
        # Linear weight
        linear_weight = max(0.0, min(1.0, (jerk - 1.0) / 9.0))
        
        # Blend
        result = smooth * (1.0 - linear_weight) + t * linear_weight
        return int(result * FP_ONE)
    
    def position_at_time_fp(start: int, distance: int, 
                            t_fp: int, jerk_fp: int) -> int:
        interp_fp = blend_jerk_fp(t_fp, jerk_fp)
        return start + (distance * interp_fp) // FP_ONE


# ============================================================
# BULK OPERATIONS (for multi-servo updates)
# ============================================================

if _HAS_VIPER:
    @micropython.viper
    def batch_interpolate(starts, distances, t_fp: int, 
                          jerk_fp: int, output, count: int):
        """
        Calculate positions for multiple servos at once.
        
        Args:
            starts: Array of start positions (int array)
            distances: Array of distances (int array)
            t_fp: Normalized time (same for all)
            jerk_fp: Jerk factor (same for all)
            output: Output array for positions
            count: Number of servos
        """
        # Pre-calculate interpolation factor (same for all)
        t: int = t_fp
        if t < 0:
            t = 0
        elif t > 65536:
            t = 65536
        
        t2: int = (t * t) >> 16
        t3: int = (t2 * t) >> 16
        t4: int = (t3 * t) >> 16
        t5: int = (t4 * t) >> 16
        smooth: int = 6 * t5 - 15 * t4 + 10 * t3
        
        jerk: int = jerk_fp
        linear_weight: int = (jerk - 65536) * 65536 // (9 * 65536)
        if linear_weight < 0:
            linear_weight = 0
        elif linear_weight > 65536:
            linear_weight = 65536
        
        smooth_weight: int = 65536 - linear_weight
        interp: int = ((smooth * smooth_weight) >> 16) + ((t * linear_weight) >> 16)
        
        # Apply to each servo
        starts_ptr = ptr32(starts)
        dist_ptr = ptr32(distances)
        out_ptr = ptr32(output)
        
        for i in range(count):
            s: int = starts_ptr[i]
            d: int = dist_ptr[i]
            out_ptr[i] = s + ((d * interp) >> 16)

else:
    def batch_interpolate(starts, distances, t_fp: int, 
                          jerk_fp: int, output, count: int):
        interp_fp = blend_jerk_fp(t_fp, jerk_fp)
        for i in range(count):
            output[i] = starts[i] + (distances[i] * interp_fp) // FP_ONE


# ============================================================
# NATIVE DECORATED FUNCTIONS (faster than Python, slower than Viper)
# ============================================================

if _HAS_VIPER:
    @micropython.native
    def interpolate_position(start: int, end: int, t: float, jerk: float) -> int:
        """
        Native-optimized position interpolation.
        
        Use this when you need float interface but want speed.
        """
        t_fp = int(t * 65536)
        jerk_fp = int(jerk * 65536)
        distance = end - start
        return position_at_time_fp(start, distance, t_fp, jerk_fp)
else:
    def interpolate_position(start: int, end: int, t: float, jerk: float) -> int:
        t = max(0.0, min(1.0, t))
        t3 = t * t * t
        t4 = t3 * t
        t5 = t4 * t
        smooth = 6 * t5 - 15 * t4 + 10 * t3
        
        linear_weight = max(0.0, min(1.0, (jerk - 1.0) / 9.0))
        interp = smooth * (1.0 - linear_weight) + t * linear_weight
        
        return int(start + (end - start) * interp)


"""
Animation Scheduler

Provides frame-rate controlled motion scheduling for smooth animations.
Designed to run at a consistent rate (e.g., 30 FPS) and dispatch
position updates to all servos.

Features:
- Configurable frame rate
- Timer-based or polling-based operation
- Animation sequence support
- Callback hooks for status updates
- **Motion interrupts with smooth blending**

## Blocking vs Non-Blocking Usage

### Blocking (simple, no interrupts):
    scheduler = Scheduler(bus, fps=30)
    scheduler.animate({1: 2048, 2: 1024}, duration_ms=500)
    scheduler.run_until_complete()  # Blocks until done

### Non-Blocking (allows interrupts):
    scheduler = Scheduler(bus, fps=30)
    scheduler.animate({1: 2048, 2: 1024}, duration_ms=500)
    
    while scheduler.is_animating:
        scheduler.tick()  # Process one frame
        
        # Check for new commands from external source
        if new_target_received:
            # Smooth interrupt to new target!
            scheduler.interrupt(1, new_position, duration_ms=300, jerk=2.0)
        
        time.sleep_ms(scheduler.frame_ms)

### Interrupt mid-motion:
    # While animation is running, smoothly transition to new target
    scheduler.interrupt(servo_id, new_position, duration_ms=300)
    
    # Or interrupt all servos
    scheduler.interrupt_all({1: 500, 2: 1500}, duration_ms=300)
"""

import time


class Animation:
    """
    Represents a coordinated multi-servo animation sequence.
    """
    
    def __init__(self, name: str = ""):
        self.name = name
        self.keyframes = []  # List of (time_ms, {servo_id: position})
        self._current_index = 0
        self._start_time = 0
    
    def add_keyframe(self, time_ms: int, positions: dict) -> None:
        """
        Add a keyframe to the animation.
        
        Args:
            time_ms: Time from start of animation (milliseconds)
            positions: Dict of {servo_id: position}
        """
        self.keyframes.append((time_ms, positions))
        # Keep sorted by time
        self.keyframes.sort(key=lambda x: x[0])
    
    def clear(self) -> None:
        """Clear all keyframes."""
        self.keyframes.clear()
        self._current_index = 0
    
    @property
    def duration(self) -> int:
        """Total duration of animation in milliseconds."""
        if not self.keyframes:
            return 0
        return self.keyframes[-1][0]
    
    def start(self) -> None:
        """Start the animation from the beginning."""
        self._current_index = 0
        self._start_time = time.ticks_ms()
    
    def elapsed(self) -> int:
        """Get elapsed time since animation started."""
        return time.ticks_diff(time.ticks_ms(), self._start_time)
    
    def is_complete(self) -> bool:
        """Check if animation has completed."""
        return self._current_index >= len(self.keyframes)
    
    def get_next_keyframe(self) -> tuple:
        """
        Get the next keyframe if it's time.
        
        Returns:
            (time_ms, positions) tuple, or None if not time yet
        """
        if self._current_index >= len(self.keyframes):
            return None
        
        time_ms, positions = self.keyframes[self._current_index]
        
        if self.elapsed() >= time_ms:
            self._current_index += 1
            return (time_ms, positions)
        
        return None


class Scheduler:
    """
    Frame-rate controlled animation scheduler.
    
    Manages timing for consistent animation updates across
    multiple servos. Supports smooth motion interrupts.
    """
    
    def __init__(self, bus, fps: int = 30):
        """
        Initialize scheduler.
        
        Args:
            bus: ServoBus instance
            fps: Target frame rate (frames per second)
        """
        self._bus = bus
        self._fps = fps
        self._frame_ms = 1000 // fps
        self._running = False
        self._last_frame = 0
        
        # Callbacks
        self._on_frame = None
        self._on_complete = None
        
        # Current animation
        self._animation = None
        
        # Motion state tracking for smooth interrupts
        # servo_id -> {position, velocity, last_update}
        self._motion_states = {}
        
        # Stats
        self._frame_count = 0
        self._dropped_frames = 0
        self._last_frame_time_us = 0
    
    @property
    def frame_ms(self) -> int:
        """Get frame duration in milliseconds."""
        return self._frame_ms
    
    @property
    def fps(self) -> int:
        """Get target frame rate."""
        return self._fps
    
    @fps.setter
    def fps(self, value: int) -> None:
        """Set target frame rate."""
        self._fps = max(1, min(120, value))
        self._frame_ms = 1000 // self._fps
        self._bus.frame_rate = self._fps
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running
    
    @property
    def is_animating(self) -> bool:
        """Check if there are active motions."""
        for state in self._bus._servos.values():
            if state.motion_queue.is_moving or state.has_pending():
                return True
        return False
    
    def on_frame(self, callback) -> None:
        """
        Set callback for each frame.
        
        Callback receives (frame_count, elapsed_ms).
        """
        self._on_frame = callback
    
    def on_complete(self, callback) -> None:
        """
        Set callback when all animations complete.
        
        Callback receives no arguments.
        """
        self._on_complete = callback
    
    # ============================================================
    # ANIMATION METHODS
    # ============================================================
    
    def animate(self, moves: dict, duration_ms: int = None,
                jerk: float = 1.0) -> None:
        """
        Start animated moves for multiple servos.
        
        Args:
            moves: Dict of {servo_id: target_position} or
                   {servo_id: (position, duration_ms)} for per-servo timing
            duration_ms: Default duration for all moves (if not per-servo)
            jerk: Jerk factor for S-curve moves
        """
        for servo_id, target in moves.items():
            if isinstance(target, tuple):
                pos, dur = target
            else:
                pos = target
                dur = duration_ms or 500
            
            self._bus.queue_move(servo_id, pos, dur, jerk)
    
    def animate_degrees(self, moves: dict, duration_ms: int = None,
                        jerk: float = 1.0) -> None:
        """
        Start animated moves in degrees.
        
        Args:
            moves: Dict of {servo_id: target_degrees}
            duration_ms: Default duration
            jerk: Jerk factor
        """
        for servo_id, degrees in moves.items():
            if isinstance(degrees, tuple):
                deg, dur = degrees
            else:
                deg = degrees
                dur = duration_ms or 500
            
            self._bus.queue_move_degrees(servo_id, deg, dur, jerk)
    
    def play_animation(self, animation: Animation, jerk: float = 1.0) -> None:
        """
        Start playing an animation sequence.
        
        Args:
            animation: Animation object with keyframes
            jerk: Jerk factor for moves
        """
        self._animation = animation
        self._animation.start()
        self._animation_jerk = jerk
    
    def stop_animation(self) -> None:
        """Stop current animation."""
        self._animation = None
        self._bus.stop_all()
    
    # ============================================================
    # MOTION INTERRUPTS
    # ============================================================
    
    def interrupt(self, servo_id: int, target_pos: int,
                  duration_ms: int = 300, jerk: float = 2.0) -> bool:
        """
        Smoothly interrupt current motion and transition to new target.
        
        This is the key method for responsive motion control. It:
        1. Estimates current position and velocity from active motion
        2. Creates a new blended motion profile that starts from current state
        3. Replaces the current motion queue with the new profile
        
        Args:
            servo_id: Servo to interrupt
            target_pos: New target position
            duration_ms: Duration of transition (shorter = snappier)
            jerk: Jerk factor (higher = snappier response)
        
        Returns:
            True if interrupt was applied, False if servo not found
        
        Example:
            # User is animating to position 2048 over 1 second
            scheduler.animate({1: 2048}, duration_ms=1000)
            
            # 300ms later, new input arrives - go to 500 instead!
            scheduler.interrupt(1, 500, duration_ms=300, jerk=2.0)
            # Servo smoothly redirects mid-flight
        """
        state = self._bus.get_servo(servo_id)
        if state is None:
            return False
        
        # Get current motion state
        current_pos, current_vel = self._get_motion_state(servo_id)
        
        # Clear existing motion queue
        state.motion_queue.clear()
        state.clear_pending()
        
        # Import blending module
        try:
            from .blending import BlendableProfile
        except ImportError:
            # Fallback: just queue a regular move from current position
            self._bus.queue_move(servo_id, target_pos, duration_ms, jerk)
            return True
        
        # Create blended profile starting from current velocity
        profile = BlendableProfile(
            start_pos=current_pos,
            start_vel=current_vel,
            end_pos=target_pos,
            end_vel=0.0,  # Stop at target
            duration_ms=duration_ms,
            jerk=jerk
        )
        
        # Add to motion queue
        state.motion_queue.add(profile)
        
        return True
    
    def interrupt_all(self, targets: dict, duration_ms: int = 300,
                      jerk: float = 2.0) -> int:
        """
        Smoothly interrupt all specified servos to new targets.
        
        Args:
            targets: Dict of {servo_id: target_position}
            duration_ms: Duration of transition
            jerk: Jerk factor
        
        Returns:
            Number of servos interrupted
        """
        count = 0
        for servo_id, target_pos in targets.items():
            if self.interrupt(servo_id, target_pos, duration_ms, jerk):
                count += 1
        return count
    
    def redirect(self, servo_id: int, target_pos: int,
                 arrival_time_ms: int = None, jerk: float = 1.5) -> bool:
        """
        Redirect servo to new target, arriving at specified time.
        
        Unlike interrupt() which specifies duration, redirect() specifies
        when you want to arrive, and calculates the duration automatically.
        
        Args:
            servo_id: Servo to redirect
            target_pos: New target position
            arrival_time_ms: When to arrive (ms from now). If None, uses
                            estimated time based on distance and velocity.
            jerk: Jerk factor
        
        Returns:
            True if redirect was applied
        """
        state = self._bus.get_servo(servo_id)
        if state is None:
            return False
        
        current_pos, current_vel = self._get_motion_state(servo_id)
        distance = abs(target_pos - current_pos)
        
        if arrival_time_ms is None:
            # Estimate reasonable duration based on distance
            # Assume ~1000 ticks/second base speed
            base_duration = (distance / 1000) * 1000  # ms
            arrival_time_ms = max(100, min(2000, int(base_duration)))
        
        return self.interrupt(servo_id, target_pos, arrival_time_ms, jerk)
    
    def _get_motion_state(self, servo_id: int) -> tuple:
        """
        Get current position and velocity for a servo.
        
        Returns:
            (position, velocity) tuple
        """
        state = self._bus.get_servo(servo_id)
        if state is None:
            return (0, 0.0)
        
        # Check if there's an active motion profile
        if state.motion_queue._current is not None:
            profile = state.motion_queue._current
            if hasattr(profile, 'current_velocity'):
                # BlendableProfile or similar with velocity tracking
                return (profile.current_position(), profile.current_velocity())
            else:
                # Regular profile - estimate velocity from position change
                pos = profile.current_position()
                # Estimate velocity from recent movement
                if servo_id in self._motion_states:
                    prev = self._motion_states[servo_id]
                    dt = (time.ticks_ms() - prev['time']) / 1000.0
                    if dt > 0 and dt < 0.5:
                        vel = (pos - prev['pos']) / dt
                        self._motion_states[servo_id] = {'pos': pos, 'time': time.ticks_ms(), 'vel': vel}
                        return (pos, vel)
                
                self._motion_states[servo_id] = {'pos': pos, 'time': time.ticks_ms(), 'vel': 0.0}
                return (pos, 0.0)
        
        # No active motion - use cached state
        return (state.current_position, 0.0)
    
    def _update_motion_states(self) -> None:
        """Update motion state tracking for all servos."""
        now = time.ticks_ms()
        for servo_id, state in self._bus._servos.items():
            if state.motion_queue._current is not None:
                profile = state.motion_queue._current
                pos = profile.current_position()
                
                if servo_id in self._motion_states:
                    prev = self._motion_states[servo_id]
                    dt = (now - prev['time']) / 1000.0
                    if dt > 0:
                        vel = (pos - prev['pos']) / dt
                        self._motion_states[servo_id] = {'pos': pos, 'time': now, 'vel': vel}
                else:
                    self._motion_states[servo_id] = {'pos': pos, 'time': now, 'vel': 0.0}
    
    # ============================================================
    # FRAME LOOP
    # ============================================================
    
    def tick(self) -> bool:
        """
        Process one frame tick.
        
        Call this at your desired rate, or use run() for automatic timing.
        
        Returns:
            True if there are active animations, False if idle
        """
        now = time.ticks_ms()
        frame_start_us = time.ticks_us()
        
        # Check for animation keyframes
        if self._animation is not None:
            keyframe = self._animation.get_next_keyframe()
            if keyframe is not None:
                time_ms, positions = keyframe
                
                # Calculate duration to next keyframe
                next_time = self._animation.duration
                for t, p in self._animation.keyframes[self._animation._current_index:]:
                    next_time = t
                    break
                
                duration = next_time - time_ms
                if duration <= 0:
                    duration = 100  # Minimum
                
                # Queue moves
                for servo_id, pos in positions.items():
                    self._bus.queue_move(servo_id, pos, duration, 
                                         getattr(self, '_animation_jerk', 1.0))
            
            if self._animation.is_complete():
                self._animation = None
        
        # Update motion queues and execute
        moving = self._bus.update()
        
        # Track motion states for smooth interrupts
        self._update_motion_states()
        
        # Frame callback
        if self._on_frame:
            elapsed = time.ticks_diff(now, self._last_frame) if self._last_frame else 0
            self._on_frame(self._frame_count, elapsed)
        
        # Track timing
        self._frame_count += 1
        frame_time_us = time.ticks_diff(time.ticks_us(), frame_start_us)
        self._last_frame_time_us = frame_time_us
        self._last_frame = now
        
        # Check if still animating
        still_active = moving > 0 or self._animation is not None
        
        if not still_active and self._on_complete:
            self._on_complete()
        
        return still_active
    
    def run(self) -> None:
        """
        Start the scheduler loop.
        
        Runs until stop() is called. Maintains target frame rate.
        """
        self._running = True
        self._last_frame = time.ticks_ms()
        
        while self._running:
            frame_start = time.ticks_ms()
            
            self.tick()
            
            # Maintain frame rate
            frame_time = time.ticks_diff(time.ticks_ms(), frame_start)
            if frame_time < self._frame_ms:
                time.sleep_ms(self._frame_ms - frame_time)
            else:
                self._dropped_frames += 1
    
    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
    
    def run_until_complete(self, timeout_ms: int = None) -> bool:
        """
        Run until all animations complete.
        
        Args:
            timeout_ms: Maximum time to wait (None = no timeout)
        
        Returns:
            True if completed, False if timed out
        """
        start = time.ticks_ms()
        
        while self.is_animating or self._animation is not None:
            frame_start = time.ticks_ms()
            
            self.tick()
            
            # Check timeout
            if timeout_ms is not None:
                if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
                    return False
            
            # Maintain frame rate
            frame_time = time.ticks_diff(time.ticks_ms(), frame_start)
            if frame_time < self._frame_ms:
                time.sleep_ms(self._frame_ms - frame_time)
        
        return True
    
    def run_frames(self, count: int) -> None:
        """
        Run a specific number of frames.
        
        Args:
            count: Number of frames to run
        """
        for _ in range(count):
            frame_start = time.ticks_ms()
            
            self.tick()
            
            frame_time = time.ticks_diff(time.ticks_ms(), frame_start)
            if frame_time < self._frame_ms:
                time.sleep_ms(self._frame_ms - frame_time)
    
    # ============================================================
    # STATS
    # ============================================================
    
    def stats(self) -> dict:
        """Get scheduler statistics."""
        return {
            'fps': self._fps,
            'frame_count': self._frame_count,
            'dropped_frames': self._dropped_frames,
            'last_frame_us': self._last_frame_time_us,
            'is_running': self._running,
            'is_animating': self.is_animating,
        }
    
    def reset_stats(self) -> None:
        """Reset frame statistics."""
        self._frame_count = 0
        self._dropped_frames = 0


def create_wave_animation(servo_ids: list, amplitude: int,
                          period_ms: int, cycles: int = 1,
                          phase_offset: float = 0.25) -> Animation:
    """
    Create a wave animation across multiple servos.
    
    Servos will move in a wave pattern with phase offsets.
    
    Args:
        servo_ids: List of servo IDs to animate
        amplitude: Motion amplitude in ticks
        period_ms: Wave period in milliseconds
        cycles: Number of complete cycles
        phase_offset: Phase offset between adjacent servos (0-1)
    
    Returns:
        Animation object ready to play
    """
    import math
    
    anim = Animation("wave")
    num_servos = len(servo_ids)
    steps_per_cycle = 20  # Resolution
    
    for cycle in range(cycles):
        for step in range(steps_per_cycle):
            time_ms = (cycle * period_ms) + (step * period_ms // steps_per_cycle)
            positions = {}
            
            for i, servo_id in enumerate(servo_ids):
                # Calculate phase for this servo
                phase = (step / steps_per_cycle) + (i * phase_offset)
                phase = phase % 1.0
                
                # Sine wave position
                pos = int(amplitude * math.sin(phase * 2 * math.pi))
                positions[servo_id] = pos + amplitude  # Offset to positive
            
            anim.add_keyframe(time_ms, positions)
    
    return anim


import time
from feetech_servo import FeetechServo, REG_TORQUE_ENABLE

def test_offset():
    servo = FeetechServo()
    port = FeetechServo.auto_detect_port()
    if not port:
        print("No port found")
        return
    servo.open(port, 1000000)
    
    sid = 9
    servo.configure_for_type('sts')
    
    print("Enabling torque...")
    servo.enable_torque(sid, True)
    time.sleep(0.5)
    
    pos1 = servo.read_position_signed(sid)
    off1 = servo.read_register(sid, 31)
    print(f"Initial: Pos={pos1}, Offset={off1}")
    
    new_off = off1 + 100
    print(f"Setting offset to {new_off} (without moving goal)...")
    
    # Just write offset and see what happens to position over time
    servo.disable_torque(sid)
    servo.unlock_eprom(sid, 'sts')
    servo.write_register(sid, 31, new_off)
    servo.lock_eprom(sid, 'sts')
    servo.enable_torque(sid, True)
    
    for i in range(10):
        pos = servo.read_position_signed(sid)
        print(f"  t={i*0.1:.1f}s: Pos={pos}")
        time.sleep(0.1)

    print("Restoring offset...")
    servo.disable_torque(sid)
    servo.unlock_eprom(sid, 'sts')
    servo.write_register(sid, 31, off1)
    servo.lock_eprom(sid, 'sts')
    servo.enable_torque(sid, True)
    
    for i in range(5):
        pos = servo.read_position_signed(sid)
        print(f"  t={i*0.1:.1f}s: Pos={pos}")
        time.sleep(0.1)

    servo.close()

if __name__ == '__main__':
    test_offset()
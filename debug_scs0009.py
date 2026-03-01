import time
import sys
import platform

if platform.system() == 'Windows':
    import msvcrt
    def check_key():
        if msvcrt.kbhit():
            return msvcrt.getch()
        return None
else:
    import select
    def check_key():
        dr,dw,de = select.select([sys.stdin], [], [], 0)
        if not dr:
            return None
        return sys.stdin.read(1)

from feetech_servo import FeetechServo, REG_PRESENT_POSITION, REG_PRESENT_LOAD, REG_MOVING

def main():
    servo = FeetechServo()
    port = FeetechServo.auto_detect_port()
    if not port:
        print("No port found")
        return
    servo.open(port, 1000000)
    
    scs_id = 20
    servo.configure_for_type('scs')
    
    # Disable torque first to ensure it's relaxed
    servo.disable_torque(scs_id)
    time.sleep(0.5)
    
    print("Reading position repeatedly with TORQUE OFF...")
    print("Press 'q' to quit.")
    
    try:
        while True:
            key = check_key()
            if key and key.lower() in [b'q', 'q']:
                break
                
            pos = servo.read_position(scs_id)
            print(f"Current Position (Torque OFF): {pos:4}", end='\r')
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nExiting...")
        servo.close()

if __name__ == '__main__':
    main()

import time
from feetech_servo import FeetechServo

def check_readings():
    servo = FeetechServo()
    port = FeetechServo.auto_detect_port()
    if not port:
        print("No port")
        return
    servo.open(port, 1000000)
    
    sts_id = 9
    scs_id = 20

    for _ in range(5):
        servo.configure_for_type('sts')
        sts_pos = servo.read_position(sts_id)
        
        servo.configure_for_type('scs')
        scs_pos = servo.read_position(scs_id)
        
        print(f"STS: {sts_pos}, SCS: {scs_pos}")
        time.sleep(0.5)

if __name__ == "__main__":
    check_readings()

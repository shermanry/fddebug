import time
import sys
import platform

# For capturing single keypresses without requiring enter
if platform.system() == 'Windows':
    import msvcrt
    def wait_for_space(prompt="Press SPACE to proceed (or Q to quit)..."):
        print(f"\n[?] {prompt}", end='', flush=True)
        while True:
            key = msvcrt.getch()
            if key == b' ':
                print()  # newline
                return True
            elif key.lower() == b'q':
                print("\n[!] Quitting...")
                return False
else:
    # Fallback for non-Windows
    import tty, termios
    def wait_for_space(prompt="Press SPACE to proceed (or Q to quit)..."):
        print(f"\n[?] {prompt}", end='', flush=True)
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                ch = sys.stdin.read(1)
                if ch == ' ':
                    print()
                    return True
                elif ch.lower() == 'q':
                    print("\n[!] Quitting...")
                    return False
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

from feetech_servo import FeetechServo

def main():
    print("="*60)
    print(" Feetech Servo Interactive Integration Test ")
    print("="*60)

    servo = FeetechServo()
    
    print("\n[*] Finding servo port...")
    port = FeetechServo.auto_detect_port()
    if not port:
        print("[!] No servo adapter found. Please connect the URT-1.")
        return
        
    print(f"[*] Connecting to {port} at 1000000 baud...")
    if not servo.open(port, 1000000):
        print("[!] Failed to open port.")
        return

    sts_id = 9
    scs_id = 20

    def safe_exit():
        print("\n[!] Safely exiting... Disabling torque on all servos.")
        servo.configure_for_type('sts')
        servo.disable_torque(sts_id)
        servo.configure_for_type('scs')
        servo.disable_torque(scs_id)
        servo.close()
        sys.exit(0)

    try:
        print("\n--- Initializing & Checking Connection ---")
        
        # Ping STS3215
        servo.configure_for_type('sts')
        if servo.ping(sts_id) < 0:
            print(f"[!] Warning: STS3215 (ID {sts_id}) NOT found!")
        else:
            print(f"[*] STS3215 (ID {sts_id}) found successfully.")

        # Ping SCS0009
        servo.configure_for_type('scs')
        if servo.ping(scs_id) < 0:
            print(f"[!] Warning: SCS0009 (ID {scs_id}) NOT found!")
        else:
            print(f"[*] SCS0009 (ID {scs_id}) found successfully.")

        # ---------------------------------------------------------
        # STEP 1: Torque Off & Manual Movement
        # ---------------------------------------------------------
        if not wait_for_space("Step 1: I will now DISABLE torque. Both servos should become loose.\n    Press SPACE to execute..."): safe_exit()
        servo.configure_for_type('sts')
        servo.disable_torque(sts_id)
        servo.configure_for_type('scs')
        servo.disable_torque(scs_id)
        
        if not wait_for_space("    -> Now, manually rotate both servo horns to a random position.\n    Press SPACE when done to read their positions..."): safe_exit()
        
        servo.configure_for_type('sts')
        sts_pos = servo.read_position(sts_id)
        servo.configure_for_type('scs')
        scs_pos = servo.read_position(scs_id)
        print(f"    [*] STS3215 Position: {sts_pos} (0-4095 scale)")
        print(f"    [*] SCS0009 Position: {scs_pos} (0-1023 scale)")

        # ---------------------------------------------------------
        # STEP 2: Torque On & Hold
        # ---------------------------------------------------------
        if not wait_for_space("Step 2: I will now ENABLE torque. Both servos should become stiff and hold position.\n    Press SPACE to execute..."): safe_exit()
        
        # Read the current positions first so they don't jump suddenly
        servo.configure_for_type('sts')
        current_sts = servo.read_position(sts_id)
        if current_sts >= 0:
            servo.write_position(sts_id, current_sts)
        servo.enable_torque(sts_id)
        
        servo.configure_for_type('scs')
        current_scs = servo.read_position(scs_id)
        if current_scs >= 0:
            servo.write_position(scs_id, current_scs)
        servo.enable_torque(scs_id)
        
        print("    [*] Torque Enabled. Try gently moving them, they should resist.")

        # ---------------------------------------------------------
        # STEP 3: Centering
        # ---------------------------------------------------------
        if not wait_for_space("Step 3: Moving to CENTER. STS3215 -> 2048, SCS0009 -> 512.\n    Press SPACE to move..."): safe_exit()
        servo.configure_for_type('sts')
        servo.write_position(sts_id, 2048, speed=600)
        servo.configure_for_type('scs')
        servo.write_position(scs_id, 512, speed=300)
        
        time.sleep(1.5)
        
        servo.configure_for_type('sts')
        sts_pos = servo.read_position(sts_id)
        servo.configure_for_type('scs')
        scs_pos = servo.read_position(scs_id)
        print(f"    [*] STS3215 is at: {sts_pos} (Expected ~2048)")
        print(f"    [*] SCS0009 is at: {scs_pos} (Expected ~512)")

        # ---------------------------------------------------------
        # STEP 4: Limit Movements
        # ---------------------------------------------------------
        if not wait_for_space("Step 4: Moving to OFFSET positions. STS3215 -> 1000, SCS0009 -> 200.\n    Press SPACE to move..."): safe_exit()
        servo.configure_for_type('sts')
        servo.write_position(sts_id, 1000, speed=800)
        servo.configure_for_type('scs')
        servo.write_position(scs_id, 200, speed=400)
        
        time.sleep(1.5)
        
        servo.configure_for_type('sts')
        sts_pos = servo.read_position(sts_id)
        servo.configure_for_type('scs')
        scs_pos = servo.read_position(scs_id)
        print(f"    [*] STS3215 is at: {sts_pos} (Expected ~1000)")
        print(f"    [*] SCS0009 is at: {scs_pos} (Expected ~200)")

        # ---------------------------------------------------------
        # STEP 5: Telemetry Reading
        # ---------------------------------------------------------
        if not wait_for_space("Step 5: Reading Telemetry (Voltage & Temperature).\n    Press SPACE to read..."): safe_exit()
        
        servo.configure_for_type('sts')
        print(f"    [*] STS3215 Telemetry: {servo.read_voltage(sts_id)}V, {servo.read_temperature(sts_id)}°C")
        
        servo.configure_for_type('scs')
        print(f"    [*] SCS0009 Telemetry: {servo.read_voltage(scs_id)}V, {servo.read_temperature(scs_id)}°C")

        # ---------------------------------------------------------
        # STEP 6: Teardown
        # ---------------------------------------------------------
        if not wait_for_space("Step 6: Finish & Teardown. I will disable torque and exit.\n    Press SPACE to finish..."): safe_exit()
        
        safe_exit()

    except KeyboardInterrupt:
        safe_exit()

if __name__ == '__main__':
    main()

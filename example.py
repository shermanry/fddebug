#!/usr/bin/env python3
"""
Example usage of Feetech Servo Controller

This demonstrates basic servo control with the URT-1 debugger on macOS.
Tested with SCS0009 servo.
"""

from feetech_servo import FeetechServo, FeetechSCS, FeetechSMS
import time


def basic_example():
    """Basic servo control example for SCS0009"""
    
    # Create controller (default is now big-endian, correct for SCS series)
    servo = FeetechServo()  # or FeetechSCS() for explicit SCS support
    
    # List available ports
    print("=== Available Serial Ports ===")
    ports = servo.find_ports()
    
    if not ports:
        print("No serial ports found! Make sure URT-1 is connected.")
        return
    
    # Open connection (adjust port name for your system)
    # Common port names:
    #   macOS: /dev/tty.usbserial-XXXX or /dev/tty.wchusbserial-XXXX
    #   Linux: /dev/ttyUSB0
    
    port = None
    for p in ports:
        if 'usbserial' in p['device'] or 'ttyUSB' in p['device']:
            port = p['device']
            break
    
    if not port:
        print("Could not find URT-1 device. Please specify port manually.")
        return
    
    print(f"\n=== Connecting to {port} ===")
    if not servo.open(port, baudrate=1000000):
        print("Failed to open port!")
        return
    
    try:
        # Scan for connected servos
        print("\n=== Scanning for Servos ===")
        found = servo.scan(1, 10)  # Scan IDs 1-10
        
        if not found:
            print("No servos found! Check wiring and power.")
            return
        
        servo_id = found[0]
        print(f"\n=== Testing Servo ID {servo_id} ===")
        
        # Read current status
        status = servo.get_status(servo_id)
        if status:
            print(f"Current position: {status.position}")
            print(f"Voltage: {status.voltage}V")
            print(f"Temperature: {status.temperature}°C")
        
        # Move servo back and forth
        print("\n=== Movement Test ===")
        
        # Move to position 200
        print("Moving to position 200...")
        servo.write_position(servo_id, 200, speed=500)
        time.sleep(1)
        
        # Read new position
        pos = servo.read_position(servo_id)
        print(f"Current position: {pos}")
        
        # Move to position 800
        print("Moving to position 800...")
        servo.write_position(servo_id, 800, speed=500)
        time.sleep(1)
        
        pos = servo.read_position(servo_id)
        print(f"Current position: {pos}")
        
        # Return to center
        print("Moving to center (512)...")
        servo.write_position(servo_id, 512, speed=500)
        time.sleep(1)
        
        print("\n=== Test Complete ===")
        
    finally:
        servo.close()


def sync_write_example():
    """Example of controlling multiple servos simultaneously"""
    
    servo = FeetechServo()
    
    # Open your port
    if not servo.open('/dev/tty.usbserial-1410'):  # Adjust port name
        print("Failed to open port")
        return
    
    try:
        # Move servos 1, 2, and 3 simultaneously
        servos = [
            (1, 200, 0, 500),   # ID 1 -> position 200, speed 500
            (2, 512, 0, 500),   # ID 2 -> position 512, speed 500
            (3, 800, 0, 500),   # ID 3 -> position 800, speed 500
        ]
        
        print("Moving multiple servos...")
        servo.sync_write_position(servos)
        time.sleep(1)
        
        # Move all to center
        servos = [
            (1, 512, 0, 500),
            (2, 512, 0, 500),
            (3, 512, 0, 500),
        ]
        servo.sync_write_position(servos)
        
    finally:
        servo.close()


def wheel_mode_example():
    """Example of continuous rotation (wheel) mode for SMS/STS servos"""
    
    servo = FeetechSMS()  # Use SMS controller for SMS/STS series
    
    if not servo.open('/dev/tty.usbserial-1410'):  # Adjust port name
        print("Failed to open port")
        return
    
    try:
        servo_id = 1
        
        # Enable wheel mode
        print("Enabling wheel mode...")
        servo.wheel_mode(servo_id)
        
        # Spin forward
        print("Spinning forward...")
        servo.write_speed(servo_id, 500)
        time.sleep(2)
        
        # Spin backward
        print("Spinning backward...")
        servo.write_speed(servo_id, -500)
        time.sleep(2)
        
        # Stop
        print("Stopping...")
        servo.write_speed(servo_id, 0)
        
        # Return to servo mode
        print("Returning to servo mode...")
        servo.servo_mode(servo_id)
        
    finally:
        servo.close()


if __name__ == '__main__':
    basic_example()


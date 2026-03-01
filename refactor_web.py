import os

def refactor():
    filepath = 'servo_web.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Address mapping for what was in servo_web.py
    replacements = {
        'SCSReg.MIN_ANGLE_LIMIT_L': '9',
        'SCSReg.MAX_ANGLE_LIMIT_L': '11',
        'SCSReg.TORQUE_ENABLE': '40',
        'SCSReg.BAUD_RATE': '6',
        'SCSReg.CW_DEAD': '26',
        'SCSReg.CCW_DEAD': '27',
        'SCSReg.P_COEFFICIENT': '21',
        'SCSReg.I_COEFFICIENT': '22',
        'SCSReg.D_COEFFICIENT': '23',
        'SCSReg.PUNCH_L': '24',
        'SCSReg.MAX_TORQUE_L': '16',
        'SCSReg.MAX_TEMP': '13',
        'SCSReg.MIN_VOLTAGE': '15',
        'SCSReg.MAX_VOLTAGE': '14',
        'SCSReg.PROTECTION_TORQUE': '34',
        'SCSReg.PROTECTION_TIME': '35',
        'SCSReg.PROTECTION_CURRENT_L': '28',
        'SCSReg.LED_ALARM_CONDITION': '20',
        'SCSReg.UNLOADING_CONDITION': '19',
        'SCSReg.SPEED_CLOSED_LOOP_P': '37',
        'SCSReg.VELOCITY_I': '39',
        'SMSReg.ACC': '41',
        'SCSReg, SMSReg, ': '',
        'SCSReg, ': '',
        ', SCSReg': '',
        'SMSReg, ': '',
        ', SMSReg': '',
    }

    for old, new in replacements.items():
        content = content.replace(old, new)
        
    # Now replace method calls:
    # servo.read_byte(..., 40) -> servo.read_register(..., 40)
    # servo.read_word_signed(..., 9) -> servo.read_register(..., 9)
    # servo.read_word(..., 9) -> servo.read_register(..., 9)
    # servo.write_byte(..., 40, value) -> servo.write_register(..., 40, value)
    # servo.write_word_signed(..., 9, value) -> servo.write_register(..., 9, value)
    # servo.write_word(..., 9, value) -> servo.write_register(..., 9, value)
    
    content = content.replace('read_byte(', 'read_register(')
    content = content.replace('read_word_signed(', 'read_register(')
    content = content.replace('read_word(', 'read_register(')
    
    content = content.replace('write_byte(', 'write_register(')
    content = content.replace('write_word_signed(', 'write_register(')
    content = content.replace('write_word(', 'write_register(')
    
    # Wait, some calls like min(0, value) or max(0, value) for write_register 
    # might still exist from old logic. We can just leave them or they will still work.
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Refactored servo_web.py")

if __name__ == '__main__':
    refactor()

import os

def refactor():
    filepath = 'feetech_servo.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    replacements = {
        'SCSReg.ID': 'REG_ID',
        'SCSReg.BAUD_RATE': 'REG_BAUD_RATE',
        'SCSReg.MIN_ANGLE_LIMIT_L': 'REG_MIN_ANGLE',
        'SCSReg.MAX_ANGLE_LIMIT_L': 'REG_MAX_ANGLE',
        'SCSReg.OPERATION_MODE': 'REG_MODE',
        'SMSReg.MODE': 'REG_MODE',
        'SCSReg.TORQUE_ENABLE': 'REG_TORQUE_ENABLE',
        'SCSReg.ACC': 'REG_ACC',
        'SMSReg.ACC': 'REG_ACC',
        'SCSReg.GOAL_POSITION_L': 'REG_GOAL_POSITION',
        'SCSReg.GOAL_TIME_L': 'REG_GOAL_TIME',
        'SCSReg.GOAL_SPEED_L': 'REG_GOAL_SPEED',
        'SCSReg.PRESENT_POSITION_L': 'REG_PRESENT_POSITION',
        'SCSReg.PRESENT_SPEED_L': 'REG_PRESENT_SPEED',
        'SCSReg.PRESENT_LOAD_L': 'REG_PRESENT_LOAD',
        'SCSReg.PRESENT_VOLTAGE': 'REG_PRESENT_VOLTAGE',
        'SCSReg.PRESENT_TEMPERATURE': 'REG_PRESENT_TEMPERATURE',
        'SCSReg.MOVING': 'REG_MOVING',
        'SCSReg.PRESENT_CURRENT_L': 'REG_PRESENT_CURRENT',
        'SMSReg.OFS_L': 'REG_OFFSET',
        'SCSReg.LOCK': 'REG_LOCK_SCS',
        'SMSReg.LOCK': 'REG_LOCK_STS',
    }

    for old, new in replacements.items():
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Refactored references in feetech_servo.py")

if __name__ == '__main__':
    refactor()

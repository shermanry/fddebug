import pytest
import csv
import os

from feetech_servo import FeetechServo
from servo_mappings import SCS_MEMORY_MAP, STS_MEMORY_MAP

def parse_xdat(filepath):
    """Parse a Feetech .xdat memory dump file into a dictionary of {address: byte_value}"""
    memory = {}
    with open(filepath, 'rb') as f:
        data = f.read()
    i = 0
    while i < len(data):
        addr = data[i]
        length = data[i+1]
        chunk = data[i+2 : i+2+length]
        for j, b in enumerate(chunk):
            memory[addr + j] = b
        i += 2 + length
    return memory

def parse_csv(filepath):
    """Parse a Feetech mapping CSV file into a dictionary of {address: expected_data}"""
    expected = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addr = int(row['Address'])
            val = int(row['Value'])
            expected[addr] = {
                'value': val,
                'name': row['Memory'],
                'area': row['Area']
            }
    return expected

def decode_value(controller, memory, addr, reg_info):
    """Extract and decode a value from memory map using the new universal map logic."""
    size = reg_info['size']
    signed_bit = reg_info.get('signed_bit')
    
    if size == 1:
        if addr in memory:
            val = memory[addr]
        else:
            return None
    elif size == 2:
        if addr in memory and (addr + 1) in memory:
            low = memory[addr]
            high = memory[addr + 1]
            val = controller._scs2host(low, high)
        else:
            return None
    else:
        return None
        
    if val >= 0 and signed_bit is not None:
        return controller._from_sign_magnitude(val, signed_bit)
        
    return val

def test_scs0009_mapping():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    xdat_path = os.path.join(base_dir, 'rosetta_stone', 'scs0009_data.xdat')
    csv_path = os.path.join(base_dir, 'rosetta_stone', 'scs0009_mapping_fixed.csv')
    
    memory = parse_xdat(xdat_path)
    expected = parse_csv(csv_path)
    
    controller = FeetechServo(end=1) # SCS is big-endian
    
    discrepancies = []
    
    for addr, expected_data in expected.items():
        expected_val = expected_data['value']
        csv_name = expected_data['name']
        csv_area = expected_data['area']
        
        if addr not in SCS_MEMORY_MAP:
            if csv_area != 'SRAM' or addr in memory:
                discrepancies.append(f"Address {addr} ('{csv_name}', expected {expected_val}) is missing from SCS_MEMORY_MAP")
            continue
            
        info = SCS_MEMORY_MAP[addr]
        name = info['name']
        
        decoded_val = decode_value(controller, memory, addr, info)
        
        if decoded_val is None:
            if csv_area != 'SRAM':
                discrepancies.append(f"Address {addr} ({name}): Missing data in memory map for area {csv_area}")
            continue
            
        if decoded_val != expected_val:
            discrepancies.append(f"Address {addr} ({name}): memory={decoded_val}, expected={expected_val}")
            
    assert not discrepancies, "Discrepancies found in SCS0009:\n" + "\n".join(discrepancies)

def test_sts3215_mapping():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    xdat_path = os.path.join(base_dir, 'rosetta_stone', 'sts3215_data.xdat')
    csv_path = os.path.join(base_dir, 'rosetta_stone', 'sts3215_mapping.csv')
    
    memory = parse_xdat(xdat_path)
    expected = parse_csv(csv_path)
    
    controller = FeetechServo(end=0) # STS is little-endian
    
    discrepancies = []
    
    for addr, expected_data in expected.items():
        expected_val = expected_data['value']
        csv_name = expected_data['name']
        csv_area = expected_data['area']
        
        if addr not in STS_MEMORY_MAP:
            if csv_area != 'SRAM' or addr in memory:
                discrepancies.append(f"Address {addr} ('{csv_name}', expected {expected_val}) is missing from STS_MEMORY_MAP")
            continue
            
        info = STS_MEMORY_MAP[addr]
        name = info['name']
        
        decoded_val = decode_value(controller, memory, addr, info)
        
        if decoded_val is None:
            if csv_area != 'SRAM':
                discrepancies.append(f"Address {addr} ({name}): Missing data in memory map for area {csv_area}")
            continue
            
        if decoded_val != expected_val:
            discrepancies.append(f"Address {addr} ({name}): memory={decoded_val}, expected={expected_val}")
            
    assert not discrepancies, "Discrepancies found in STS3215:\n" + "\n".join(discrepancies)

if __name__ == '__main__':
    pytest.main(['-v', __file__])

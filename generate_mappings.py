import csv
import json
import os

def generate_mappings():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scs_csv = os.path.join(base_dir, 'rosetta_stone', 'scs0009_mapping_fixed.csv')
    sts_csv = os.path.join(base_dir, 'rosetta_stone', 'sts3215_mapping.csv')
    
    # Define known 2-byte registers based on Feetech specs and feetech_servo.py
    # These are addresses that are the LOW byte of a 2-byte value.
    scs_2byte = {9, 11, 16, 24, 31, 42, 44, 46, 56, 58, 60, 69}
    sts_2byte = {9, 11, 16, 24, 28, 31, 42, 44, 46, 48, 50, 52, 56, 58, 60, 69}
    
    # Define signed registers for STS (sign-magnitude encoding)
    # Using 15 for 16-bit sign-magnitude, 10 for 11-bit sign-magnitude
    sts_signed = {
        9: 15,   # Min Angle Limit
        11: 15,  # Max Angle Limit
        31: 15,  # Position Offset
        44: 10,  # Goal PWM (uses bit 10 for sign according to feetech_servo.py)
        46: 15,  # Goal Velocity
        58: 15,  # Present Velocity
    }
    
    # We'll just define any signed SCS ones if needed (none are currently signed for SCS in feetech_servo.py)
    scs_signed = {}

    def parse_csv(filepath, size_set, signed_dict):
        mapping = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                addr = int(row['Address'])
                name = row['Memory']
                area = row['Area']
                rw = row['R/W']
                
                size = 2 if addr in size_set else 1
                
                signed_bit = signed_dict.get(addr, None)
                
                mapping[addr] = {
                    'name': name,
                    'size': size,
                    'signed_bit': signed_bit,
                    'area': area,
                    'rw': rw
                }
        return mapping

    scs_map = parse_csv(scs_csv, scs_2byte, scs_signed)
    sts_map = parse_csv(sts_csv, sts_2byte, sts_signed)

    out_path = os.path.join(base_dir, 'servo_mappings.py')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('"""\n')
        f.write('Auto-generated mappings from Rosetta Stone CSVs.\n')
        f.write('Provides dictionary layouts for SCS and STS servos.\n')
        f.write('"""\n\n')
        
        f.write('SCS_MEMORY_MAP = {\n')
        for k in sorted(scs_map.keys()):
            v = scs_map[k]
            f.write(f"    {k}: {v},\n")
        f.write('}\n\n')

        f.write('STS_MEMORY_MAP = {\n')
        for k in sorted(sts_map.keys()):
            v = sts_map[k]
            f.write(f"    {k}: {v},\n")
        f.write('}\n')

    print(f"Successfully generated {out_path}")

if __name__ == '__main__':
    generate_mappings()

import os

def fix_xdats():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scs_path = os.path.join(base_dir, 'rosetta_stone', 'scs0009_data.xdat')
    sts_path = os.path.join(base_dir, 'rosetta_stone', 'sts3215_data.xdat')
    
    # Read the current contents of sts3215_data.xdat, which the user accidentally updated with the SCS0009 recovery config
    with open(sts_path, 'rb') as f:
        new_scs_data = f.read()
        
    # Write the recovery config to the correct file
    with open(scs_path, 'wb') as f:
        f.write(new_scs_data)
        
    # The original sts3215_data.xdat from the beginning of the chat
    orig_sts_hex = "0028030a0009030a0000011009680b468c28e8030c2c2f2020001000010136010155000014c8500ac8c8500701143201413201"
    
    # Restore the original STS data
    with open(sts_path, 'wb') as f:
        f.write(bytes.fromhex(orig_sts_hex))
        
    print("Files fixed.")

if __name__ == '__main__':
    fix_xdats()

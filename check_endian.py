def check():
    with open("rosetta_stone/scs0009_data.xdat", "rb") as f:
        data = f.read()
    i = 0
    mem = {}
    while i < len(data):
        addr = data[i]
        length = data[i+1]
        chunk = data[i+2:i+2+length]
        for j, b in enumerate(chunk):
            mem[addr+j] = b
        i += 2 + length
    
    # Max position limit is 1003 = 0x03EB
    print("Address 11:", hex(mem.get(11, 0)))
    print("Address 12:", hex(mem.get(12, 0)))

check()

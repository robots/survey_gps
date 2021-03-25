
from xfile import TrimbleXfile
from t4k import Trimble4000
import sys
import argparse

parser = argparse.ArgumentParser(description='Trimble 4000 loader')
parser.add_argument('--port', dest='port', action='store', type=str, default="/dev/ttyUSB0", help='Port of the receiver')
parser.add_argument('--dump', dest='file_to_dump', action='store', type=str, default=None, help='Dump memory into this file')
parser.add_argument('--prog', dest='file_to_upload', action='store', type=str, default=None, help='Firmware file to upload')
parser.add_argument('--reset', dest='do_reset', action='store_const', const=True, default=False, help='Reset at the end')

args = parser.parse_args()

memory_upload = False
memory_dump = False

if args.file_to_upload is not None:
    memory_upload = True

if args.file_to_dump is not None:
    memory_dump = True


t = Trimble4000(args.port)

found, param_data = t.autodetect()

if not found:
    print("receiver not found")
    sys.exit(0)

loader_mode, baudrate, parity = param_data

print("Found receiver", baudrate, parity)

if loader_mode == False:
    _, info = t.get_some_info()
    print(info)
    t.enter_loader()


if memory_dump:
    memblock = bytearray(b'\xff' * (0x80000+0x100))
    chunk = 64
    size = 0x80000
    for i in range(int((size)/64)):
        ret, addr, data = t.mem_read(i*64, 64)
        for j in range(64):
            memblock[addr+j] = data[j]

        print("%x" % addr)

    with open(args.file_to_dump, "wb") as fout:
        fout.write(memblock)

if memory_upload:
    xf = TrimbleXfile(args.file_to_upload)

    while True:
        addr, data = xf.next_record()
        print (addr, data)
        if addr is False:
            print("\nDone")
            break
        t.mem_write(addr, data)

        sys.stdout.write("Writing address %08x len %3d\r")
        sys.stdout.flush()

if args.do_reset:
    t.do_reset()

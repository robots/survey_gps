
from xfile import FirmwareXfile, FirmwareBin, FirmwareS19
from t4000 import Trimble4000
from t4700 import Trimble4700
import sys
import argparse

parser = argparse.ArgumentParser(description='Trimble 4000 loader')
parser.add_argument('--type', dest='type', action='store', type=str, default="", help='Type of receiver 4000 4400 4700')
parser.add_argument('--port', dest='port', action='store', type=str, default="/dev/ttyUSB0", help='Port of the receiver')
parser.add_argument('--dump', dest='file_to_dump', action='store', type=str, default=None, help='Dump memory into this file')
parser.add_argument('--opt_read', dest='read_option', action='store_const', const=True, default=False, help='read options')
parser.add_argument('--opt_prog', dest='program_option', action='store', type=str, default=None, help='program options')
parser.add_argument('--prog', dest='file_to_upload', action='store', type=str, default=None, help='Firmware file to upload')
parser.add_argument('--reset', dest='do_reset', action='store_const', const=True, default=False, help='Reset at the end')

args = parser.parse_args()

receiver = {
    '4000': Trimble4000,
    '4400': Trimble4000,
    '4700': Trimble4700,
}

fwf = None

if not args.type in receiver.keys():
    print("select correct receiver type: ", receiver.keys())
    sys.exit(0)

t = receiver[args.type](args.port)

if args.file_to_upload is not None:
    if ".X" in args.file_to_upload.upper():
        fwf = FirmwareXfile(t, args.file_to_upload)
    elif ".BIN" in args.file_to_upload.upper():
        fwf = FirmwareBin(t, args.file_to_upload)
    else:
        try:
            fwf = FirmwareS19(t, args.file_to_upload)
        except Exception as e:
            raise e

    if fwf is None:
        raise Exception("Unsupported firmware file")


found, param_data = t.autodetect()

if not found:
    print("receiver not found")
    sys.exit(0)

loader_mode, baudrate, parity = param_data

#print("Found receiver Baudrate:", baudrate, " parity:", parity)
print("Found receiver")

if loader_mode == False:
#    _, info = t.get_some_info()
#    print(info)
    t.enter_loader()

if args.read_option:
    t.options_dump()

if args.program_option is not None:
    t.options_prog(args.program_option)

if args.file_to_dump is not None:
#   fw_start, fw_size, chunk, _ = t.get_fw_info()
#
#    4700:
#    fw_start, fw_size, chunk = 0x300000, 0x80000, 64 # 4700 ram dump
#    fw_start, fw_size, chunk = 0x30a662, 0x100, 64 # options copy 
#    fw_start, fw_size, chunk = 0x37fc00, 0x100, 64 # options temporary
#    fw_start, fw_size, chunk = 0x020240, 0x1000, 64 # options in flash
#    fw_start, fw_size, chunk = 0x000000, 0xf0000, 256 # almost whole flash

    # 4000
    fw_start, fw_size, chunk = 0x700000, 0x30000, 64 

    
    memblock = bytearray(b'\xff' * fw_size)

    for i in range(int((fw_size) / chunk)):
        addr= fw_start + i * chunk
        ret, _, data = t.mem_read(addr, chunk)
        if not ret:
            print("error reading %08x" % addr)
            continue

        for j in range(chunk):
            memblock[i*chunk + j] = data[j]

        sys.stdout.write("Reading address %08x\r" % addr)
        sys.stdout.flush()

    print("\nok")

    with open(args.file_to_dump, "wb") as fout:
        fout.write(memblock)

if args.file_to_upload is not None and fwf is not None:
    if t.program_image(fwf):
        print("\nok")
    else:
        print("\nerror")

#    while True:
#        addr, data, percent = fwf.next_record()
##        print (addr, data)
#        if addr is False:
#            print("\nDone")
#            break
#
#        t.mem_write(addr, data)
#
#        sys.stdout.write("Writing address %08x\r" % addr)
#        sys.stdout.flush()


if args.do_reset:
    t.do_reset()

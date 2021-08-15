import binascii
import struct
import os

class FirmwareXfile:
    def __init__(self, receiver, fname = None):
        self.fin = open(fname, "rb")
        if not self.fin:
            raise Exception("file not found")

        self.hdr = self.fin.read(0x1c)


    def next_record(self):
        s = self.fin.read(8)
        if not len(s) == 8:
            return False, False

        xx, l, adr, adr2 = struct.unpack(">HHHH", s)

        adr = adr + (adr2<<16)
        #print("%x %x %x %x" % (xx, l, adr, adr+l))

        data = self.fin.read(l)

        if not len(data) == l:
            raise Exception("datalen", len(data), l)
        if l % 2 == 1:
            self.fin.read(1)

            
        return adr, data, 0


class FirmwareBin:
    def __init__(self, receiver, fname = None):

        fw_start, fw_size, _, fw_chunk = receiver.get_fw_info()

        self.fin = open(fname, "rb")
        if not self.fin:
            raise Exception("file not found")

        self.fin.seek(0, os.SEEK_END)
        self.total_size = self.fin.tell()
        self.fin.seek(0)

        self.chunk = fw_chunk
        self.addr = fw_start

    def next_record(self):
        data = self.fin.read(self.chunk)

        addr = self.addr
        self.addr += self.chunk

        if len(data) == 0:
            addr = False
            
        percent = self.fin.tell() * 100 / self.total_size

        return addr, data, percent

class FirmwareS19:
    def __init__(self, receiver, fname = None):
        self.fin = open(fname, "r")
        if not self.fin:
            raise Exception("file not found")

        self.fw_addr, self.fw_size, _, _ = receiver.get_fw_info()
        self.linenum = 0
        self.total_lines = 0

        #test file
        while True:
            addr, data, _ = self.next_record()
            if addr == False:
                break

        #rewind
        self.fin.seek(0)
        self.total_lines = self.linenum
        self.linenum = 0

    def next_record(self):
        while True:
            l = self.fin.readline()

            if len(l) == 0:
                return False, b''

            self.linenum += 1

            if not l[0] == 'S':
                print(l[0], l)
                raise Exception("zle")

            l = l.strip()

            bytecount = int(l[2:4], 16)
            if not len(l) >= bytecount*2 + 2+2:
                print(len(l), bytecount)
                raise Exception("line %d length problem" % (linenum))

            if l[1] == '0': #header
                #print("hdr" , l)
                continue
            elif l[1] == '1': #data 16bit addr
                addr = int(l[4:8], 16)
                idx = 8
            elif l[1] == '2': #data 24bit addr
                addr = int(l[4:10], 16)
                idx = 10
            elif l[1] == '3': #data 32bit addr
                addr = int(l[4:12], 16)
                idx = 12
            elif l[1] in ['5', '6']: # count record 
                continue
            elif l[1] in ['7', '8', '9']: # start addr record 
                continue
            else:
                print(l[1], l)
                raise Exception("unsupported S19 record")

            chksum = int(l[-2:],16)
            l1 = l[:-2]
            ch = (sum(binascii.a2b_hex(l[2:-2])) & 0xff) ^ 0xff
            if not ch == chksum:
                print(l)
                raise Exception("line %d, bad checksum is %02x should be %02x" % (linenum, chksum, ch))
                
            data = binascii.a2b_hex(l1[idx:])
            break

        percent = self.linenum * 100 / self.total_lines

        return addr, data, percent 


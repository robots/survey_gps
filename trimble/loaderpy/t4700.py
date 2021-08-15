
import struct
import serial
import time
import sys
import binascii
import os


#memory map
# 0-xx ROM
# 20000 - factory data (flash?)
# 20240 - options (64byte blocks)
# 40000 - f0000(?)  firmware

# 300000 - 37ffff - ram

# 37fc00 - 37fd7a - temporary option bytes

# 600000 - ffffff filestorage (4MB)

options = {
    0: "Handheld support",
    1: "Data logging",
    2: "Auto data logging",
    3: "CMR inputs",
    4: "CMR outputs",
    5: "RTCM inputs",
    6: "RTCM outputs",
    7: "NMEA outputs",
    8: "R17 outputs",
    9: "RTK rover",
    10: "RTK moving base",
    11: "CMR type 5",
    12: "Remote download",
    13: "External timebase",
    14: "PPS output",
    15: "JX1100 radio",
    16: "10hz sampling",
    17: "Demo receiver",
    18: "Event marker ",
    19: "4MB flash",
    20: "12 sats",
    21: "HW version",
    54: "Firmware options",
}

DEBUG_L1 = False

class Trimble4700:
    baudrates = [9600, 38400, 19200, 9600]
    parities = [serial.PARITY_NONE, serial.PARITY_ODD, serial.PARITY_EVEN]
    parities_ch = ['N', 'O', 'E']
    stopbits = [serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE, serial.STOPBITS_TWO]
    stopbits_ch = ['1', '1.5', '2']

    def __init__(self, port = "/dev/ttyUSB0"):
        self.ser = serial.Serial(port, 9600, timeout = 2, rtscts=0, dsrdtr=0)
        self.receiver = -1

        self.loaderfile = os.path.dirname(__file__) + os.path.sep + "firmwares" + os.path.sep + "4700loader.bin"

    def get_fw_info(self):
        return 0x40000, 0xc0000, 256, 16

    def autodetect(self):
        t = 3

        while True:
            #print(t)
            t -= 1
            if t == 0:
                print("4700 not found")
                break

            print("sending break")
            self.ser.send_break(duration=0.004)

            xx = self._recv_l1()
            if isinstance(xx, bool):
                time.sleep(0.5)
                continue
                #return False, None

            cmd, data = xx
            #print("%x "% cmd)
            if cmd == 0x286e:
                # data will contain bytes:
                # b'PRODUCT,4700;PORT,1,9600,9600,8,1,N,F;VERSION,1.41,12/10/2,,;COMM,DCOL,NMEA;'
                print(data)
                product, port, version, comm, _ = data.split(b';')

                self.receiver = int(product.split(b',')[1])
                
                _, portnum, portbr1, portbr2, portbyte, portstop, portparity, _ = port.split(b',')

                par = portparity.decode('ascii')
                stop = portstop.decode('ascii')
                bits = int(portbyte)
                baudrate = int(portbr1)

                self.ser.baudrate = baudrate
                self.ser.parity = self.parities[self.parities_ch.index(par)]
                self.ser.bytesize = bits
                self.ser.stopbits = self.stopbits[self.stopbits_ch.index(stop)]
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()

                #return True, (False, baudrate, par)
                break

        print("Trying loader mode")
        if self.enter_loader():
            return True, (True, '', '')
        
        # try secondary bootloader ping
        print("Trying seconday loader")
        self.ser.baudrate = 38400
        if self.do_ping():
            return True, (True, '', '')

        return False, None

    def enter_loader(self, raw=False):
        self._send_l1(0x87)
        a = self._recv_l1()
        if not a:
            return False
            raise Exception("error entering loader")

        # loader wants none parity
        self.ser.parity = serial.PARITY_NONE

        time.sleep(0.1)
        if not self.l1_ping():
            raise Exception("error ping")
        time.sleep(0.1)
        if not self.l1_ping():
            raise Exception("error ping")

        self.l1_set_baudrate()

#        print("read mem 0x41",  self.mem_read(0x41, 1))

        # upload secondary loader
        print("uploading secondary loader")
        addr = 0x310000
        with open(self.loaderfile, 'rb') as fin:
            idx = 0
            ch = 200
            while True:
                d = fin.read(ch)
                if len(d) == 0:
                    break

                self.l1_mem_write(addr+idx, d)
                idx += len(d)

                sys.stdout.write(".")
                sys.stdout.flush()

        print("ok")

        # start secondary loader
        print("starting secondary loader")
        self.l1_jump_to(addr)
        time.sleep(0.3)

        # do ping
        if not self.do_ping():
            raise Exception("l2 ping error")

        return True

    def _find_opt_block(self):
        optblk = None
        idx = 0

        while True:
            ret, _, optblk = self.mem_read(0x20240+64*idx, 64)
            if not ret:
                raise Exception("error reading1")

            if optblk[0x3e] == 0xaa:
                break

            idx+=1
            if idx > 0x3f5:
                raise Exception("no opt block found")

        if not sum(optblk[:-1]) & 0xff == optblk[-1]:
            raise Exception("option block checksum not ok")

        return idx, optblk
        
    def options_prog(self, enableopt):
#        # generate temporary options
#        opts = bytearray(b'\xff' * 380)
#        opts[0] = 0x0a
#        opts[1] = 0x0b
#        opts[2] = 0x0c
#        opts[3] = 0x0d
#        opts[4] = 0x0e
#
#        for opt in [5, 16, 20, 10, 11, 14, 19, 18, 6, 12, 21]:
#            i = opt * 6 + 6
#
#            opts[i] = 0
#            # valid from 0x0000 - day zero
#            opts[i+1] = 0
#            opts[i+2] = 0
#            # valid to 0xfffe - many days from now
#            opts[i+3] = 0xff
#            opts[i+4] = 0xfe
#
#        opts[379] = 0
#        s = sum(opts)
#        s = s & 0xff
#        opts[379] = s
#
#        if not self.mem_write(0x37fc00, opts):
#            raise Exception("aaa")

        # take current block
        idx, optblk = self._find_opt_block()
        optblk = bytearray(optblk)

        print("before")
        self._print_opts(optblk)

        # add options from argument
        for o in enableopt.split(','):
            if ":" in o:
                k1,v1 = o.split(":")
                k,v = int(k1), int(v1,16)
            else:
                k = int(o)
                v = 0

            optblk[k] = v

        print("after")
        self._print_opts(optblk)
#        return True

        self._send_l2(0x0c, optblk[:0x3e])

        cmd, data = self._recv_l2()
        if not cmd == 0x0c:
            raise Exception("aaaa")

        return True

    def _print_opts(self, optblk, printall = False):
        for i in range(0x3c):
            if optblk[i] == 0xff and printall == False:
                continue

            name = ""
            if i in options.keys():
                name = options[i]

            if name == "" and optblk[i] == 0xff:
                continue

            value = ""
            if optblk[i] == 0:
                value = "enabled"
            elif optblk[i] == 0xff:
                value = "disabled"
            else:
                value = str(optblk[i])

            print("Option %d (%s): %s" % (i, name, value))

    def options_dump(self):
        idx, optblk = self._find_opt_block()

        print("Normal options:")
        self._print_opts(optblk, printall=True)

        ret, _, opttmp = self.mem_read(0x37fc00, 190+192)
        if not ret:
            raise Exception("error reading1")

        print("Temporary options:")
        self._print_opts(opttmp[6::6])

    def program_image(self, fw):
        self.erase_sectors([0x40000, 0x60000, 0x80000, 0xa0000, 0xc0000, 0xe0000])
        
        while True:
            addr, data, percent = fw.next_record()
            if addr is False:
                print("\nDone")
                break

            if data == b'\xff'*len(data):
                continue

            sys.stdout.write("Writing address %08x size 0x%02x - %.2f%%\r" % (addr, len(data), percent))
            sys.stdout.flush()

            self.do_prog(addr, data)


        self.mem_write(0x3776e0, b'\xab')
        print("\nProgramming done, after reboot wait for filesystem format")

        return True


    def do_prog(self, addr, data):
        self._send_l2(0x03, struct.pack(">I", addr) + data)

        r = self._recv_l2()
        if isinstance(r, bool):
            raise Exception("no answer")

        cmd, data = r
        if not cmd == 0x03:
            return False

        return True

    def mem_read(self, addr, l):
        self._send_l2(0x05, struct.pack(">IH", addr, l))

        r = self._recv_l2()
        if isinstance(r, bool):
            return False, None, b''

        cmd, data = r
        if not cmd == 0x05:
            return False, cmd, data

        return True, addr, data

    def mem_write(self, addr, data):
        if len(data) == 0:
            return True
        if len(data) > 0xffff:
            raise Exception("data len > 0xffff")

        self._send_l2(0x0E, struct.pack(">IH", addr, len(data)) + data)

        cmd, _ = self._recv_l2()
        if not cmd == 0x0e:
            return False

        return True

    def erase_sectors(self, sectors):
        
        print("Erasing sectors", sectors)

        data = struct.pack(">B", len(sectors))
        for addr in sectors:
            data += struct.pack(">I", addr)

        self._send_l2(0x01, data)
        cmd, _ = self._recv_cmd_l2(0x01)
        if not cmd == 0x01:
            raise Exception("no erase answer")

        # There is bug in secondary loader, it sends 2 responses for erase command.
        # we can not expect just response 0x02 in next loop, first response will be 0x01
        # hence the _recv_cmd_l2 call

        # poll for finish
        retry = 30
        while True:
            self._send_l2(0x02)
            cmd, data = self._recv_cmd_l2(0x02)

            if not cmd == 0x02:
                raise Exception("wrong answer")

            if data[0] == 1:
                print("erase done")
                break

            retry -= 1
            if retry == 0:
                raise Exception("erase timeout")

            time.sleep(1)

            sys.stdout.write(".")
            sys.stdout.flush()

        return True

    def do_ping(self):
        self._send_l2(0x00)
        cmd, _ = self._recv_l2()
        if cmd == 0x00:
            return True
        else:
            False
            
    def do_reset(self):
        self._send_l2(0x04)
        cmd, _ = self._recv_l2()
        if cmd == 0x04:
            return True
        return False

    def _send_l2(self, cmd, data=b'', verbose = False):
        l = len(data)
#        print(l)
        o = struct.pack(">BBH", 0x02, cmd, l) + data
        s = sum(o[1:]) & 0xffff
        o += struct.pack(">HBB", s, 0x03, 0x00)

        if verbose:
            print("sending", o)

        self.ser.write(o)
      #  for i in range(len(o)):
      #      self.ser.write(o[i:i+1])
      #      time.sleep(0.001)

    def _recv_cmd_l2(self, expected_cmd, verbose = False):
        while True:
            x = self._recv_l2(verbose=verbose)
            if isinstance(x, bool):
                return x
            cmd, data = x
            if cmd == expected_cmd:
                return cmd, data

    def _recv_l2(self, verbose = False):
        t = time.time()
        while True:
            if time.time() - t > 3:
                return False

            stx = self.ser.read(1)
#            if verbose:
#                print("recv", stx)

            if stx == b'\x06':
                return True

            if len(stx) == 0:
                continue

            if not stx == b'\x02':
                continue
                return False
                raise Exception("recvd bad byte")

            if stx == b'\x02':
                break

        cmd = self.ser.read(1)
        cm, = struct.unpack(">B", cmd)
#       print("recv cmd", cmd, " cmd 0x%x" % cm)

        if True:
            lraw = self.ser.read(2)
#           print("l",lraw)
            l, = struct.unpack(">H", lraw)
            #print("l",l)

            data = b''
            if l > 0:
                data = self.ser.read(l)
                #rint("data", data)

            e = self.ser.read(3)
#           print("e",e)
            chsum, etx = struct.unpack(">HB", e)

            c = (sum(data) + sum(cmd) + sum(lraw)) & 0xffff
            if not chsum == c:
                print("bad chksum", chsum, c)

            if not etx == 3:
                print("etx", etx)

        if verbose:
            print("recv cmd 0x%x" % cm, data)

        return cm, data

    def l1_mem_read(self, addr, l):
        if l+4 > 255:
            raise Exception("l+4 > 255")

        self._send_l1(0x80, struct.pack(">IB", addr, l+4))

        r = self._recv_l1()
        if isinstance(r, bool):
            return False, None, b''

        cmd, data = r
        if not cmd == 0x92:
            return False, cmd, data

        return True, addr, data
    
    def l1_mem_write(self, addr, data):
        if len(data) == 0:
            return True
        if len(data) > 251:
            raise Exception("data len > 251")

        # where did they go wrong? (-:
        #addr = ((addr >> 16) & 0xffff) + ((addr & 0xffff) << 16)

        self._send_l1(0x81, struct.pack(">I", addr) + data)

        return self._recv_l1()

    def l1_jump_to(self, addr):
        self._send_l1(0x82, struct.pack(">I", addr))
        return self._recv_l1()

    def l1_ping(self):
        dat = b'\x05\x0a\x14\x28\x00\x00'
        self.ser.write(dat)
        x = self._recv_l1()

        if isinstance(x, bool):
            return x

        return False

    def l1_set_baudrate(self, br = 0x0e):
           # 00310000 47 f9 00 ff       lea          (0xfffc00).l,A3
           #          fc 00
           #                       LAB_00310006
           # 00310006 30 2b 00 0c       move.w       (offset DAT_00fffc0c,A3),D0w
           # 0031000a 08 00 00 07       btst.l       0x7,D0
           # 0031000e 67 f6             beq.b        LAB_00310006
           # 00310010 30 3c 00 11       move.w       #0x11,D0w
           # 00310014 37 40 00 08       move.w       D0w,(offset DAT_00fffc08,A3)
           # 00310018 4e 75             rts

        print("changing baudrate to 38400")
        program = "47 F9 00 FF FC 00 30 2B 00 0C 08 00 00 07 67 F6 30 3C 00 11 37 40 00 08 4E 75"
        data = binascii.a2b_hex(program.replace(" ", ""))

        result = self.l1_mem_write(0x310000, data)
        if not result:
            raise Exception("error uploading baudrate program")

        result = self.l1_jump_to(0x310000)
        if not result:
            raise Exception("error setting baudrate")

        self.ser.baudrate = 38400
        print("ok")

    def _send_l1(self, cmd, data=b''):
        l = len(data)
#        print(l)
        o = struct.pack(">BHB", 0x02, cmd, l) + data
        s = sum(o[1:]) & 0xff
        o += struct.pack(">BB", s, 0x03) + b'\x00\x00'

        if DEBUG_L1:
            print("sending", o)

        self.ser.write(o)
#        for i in range(len(o)):
#            self.ser.write(o[i:i+1])
#            time.sleep(0.001)

    def _recv_l1(self):
        t = time.time()
        while True:
            if time.time() - t > 3:
                return False

            stx = self.ser.read(1)
#            print("recv", stx)
            if stx == b'\x06':
                if DEBUG_L1:
                    print("recv", stx)
                return True

            if len(stx) == 0:
#                print("recv notghin")
                continue
#                return False

            if not stx == b'\x02':
                continue
                return False
                raise Exception("recvd bad byte")

            if stx == b'\x02':
                break

        cmd = self.ser.read(2)
        cm, = struct.unpack(">H", cmd)
        #print("recv cmd", cmd, " cmd 0x%x" % cm)

        if True:
            l = self.ser.read(1)
            #print("l",l)
            l, = struct.unpack(">B", l)
            #print("l",l)

            data = b''
            if l > 0:
                data = self.ser.read(l)
#                print("data", data)

            e = self.ser.read(2)
            chsum, etx = struct.unpack(">BB", e)

            c = (sum(data) + sum(cmd) + l) & 0xff
            if not chsum == c:
                print("bad chksum", chsum, c)

            if not etx == 3:
                print("etx", etx)


        if DEBUG_L1:
            print("recv cmd 0x%x" % cm, data)

        return cm, data

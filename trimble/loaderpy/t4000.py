
import struct
import serial
import time
import sys

DEBUG = False

options = {
    6: 'position statistics',
    7: 'low batt override',
    8: 'pathfinder compatibility',
    10: 'rtcm network operation (needs opt28 == 0 or 2)',
    11: 'CarPhDis',
    12: 'caltrans',
    13: 'mxl1only',
    14: 'remote download',
    15: 'demo',
    16: 'xx?',
    17: 'rt17dsab',
    18: 'local datum/zones',
    19: 'rtcm rsim interface',
    20: 'dualfreq',
    21: 'serports',
    22: 'multiple datums',
    23: 'externam timebase',
    24: 'event marker',
    25: 'pps',
    27: 'firmware update',
    28: 'rtcm input',
    29: 'rtcm output',
    30: 'sync limit',
    31: 'nmea output',
    32: 'manual survey svs',
    34: 'navigation package',
    36: 'kinematic mode',
    39: 'rtk l1',
    40: 'rtk otf = 0, oft & rpt = 1',
    41: 'ionofree',
    43: 'jx1100 driver',
    45: 'cmr type2 custom rate',
    46: 'rtk special flags',
}

class Trimble4000:
    baudrates = [9600, 38400, 19200, 9600]
    parities = [serial.PARITY_NONE, serial.PARITY_ODD, serial.PARITY_EVEN]

    def __init__(self, port = "/dev/ttyUSB0"):
        self.ser = serial.Serial(port, 9600, timeout = 2, rtscts=0, dsrdtr=0)


    def autodetect(self):
        for br in self.baudrates:
            for pr in self.parities:
                print("testing ", br, pr)
                self.ser.reset_output_buffer()
                self.ser.baudrate = br
                self.ser.parity = pr
                self.ser.reset_input_buffer()

                #self.ser.write(b'\x00' * 250)
                for i in range(250):
                    self.ser.write(b'\x00')
                    time.sleep(0.001)

                ret, cmd, data = self.mem_read(0x80000, 2)
                #print (ret, cmd, data)
                if ret == True:
                    print("receiver in remote monitor mode")
                    return True, (True, br, pr)
                elif cmd is None:
                    continue
                else:
                    print("receiver in normal mode")
                    return True, (False, br, pr)

        return False, None

    # todo: multiple ranges
    def get_fw_info(self):
        return 0, 0x80000, 64, 64
        return 0x720000, 0x20000, 64, 64

    def get_some_info(self):
        self._send(0x06)
        return self._recv()

    def enter_loader(self, raw=False):
        self._send(0x87, struct.pack("B", 0x57))
        ack = self._recv()
        if not ack:
            return False
        else:
            print("enter: ack")

        self.ser.baudrate = 9600
        self.ser.parity = serial.PARITY_NONE

        retry = 100
        while True:
            ack = self.do_ping()
            if ack == True:
                print("ping: ack!!")
                break
            else:
                print("ping not ack")
            retry -= 1
            if retry == 0:
                return False

        if raw:
            return True

        # setup chipselects
        ret = self.mem_write(0x00fffa58, b'\x10\x04\x7b\x71')
        if not ret:
            print("error writing")

        # detect platform 4000 or cheetah
        ret = self.mem_write(0x00100000, b'\x55\x55\xaa\xaa')
        if not ret:
            print("error writing")

        ret, addr, data = self.mem_read(0x00100000, 4)
        if not ret:
            return("error reading2")
        if data == b'\xaa\xaa\xaa\xaa':
            print('Cheetah/7400Msi platform')
            ret = self.mem_write(0x00fffa48, b'\x00\x05\x78\x31\x04\x05\x78\x31\x70\x05\x78\x31\x74\x05\x78\x31')
        else:
            print('SE/SSE/SSI platform')
            ret = self.mem_write(0x00fffa54, b'\x70\x07\x78\x71')
            ret = self.mem_write(0x00fffa46, b'\x07\xf5')
            ret = self.mem_write(0x00fffa58, b'\x10\x04\x7b\xf1')

    def _print_opts(self, data):
        for i in range(59):
            name = ""
            if i in options.keys():
                name = options[i]

            print("Option (%d) %s: %d" % (i, name, data[i]))

    def options_dump(self):
        ret, addr, data = self.mem_read(0x22d, 59)
        if ret == False:
            raise Exception("error reading memory")

        self._print_opts(data)

    def options_prog(self, enableopt): 
        ret, addr, data = self.mem_read(0x22d, 59)

        optblk = bytearray(data)

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

        self.mem_write(0x22d, optblk)
        self.mem_write(0x3fe, b'\xc0\xde')
        
    def mem_read(self, addr, l):
        self._send(0x82, struct.pack(">IB", addr, l))

        r = self._recv()
        if isinstance(r, bool):
            return False, None, b''

        cmd, data = r
        if not cmd == 0x92:
            return False, cmd, data

        addr, = struct.unpack(">I", data[:4])

        return True, addr, data[4:]
    
    def mem_write(self, addr, data):
        if len(data) == 0:
            return True

        # where did they go wrong? (-:
        addr = ((addr >> 16) & 0xffff) + ((addr & 0xffff) << 16)

        self._send(0x80, struct.pack(">I", addr) + data)

        return self._recv()

    def do_reset(self):
        self._send(0x88)

    def do_ping(self):
        self.ser.write(b'\x05')
        return self._recv()

    def set_baudrate(self, br = 0x0e):
        self._send(0x86, struct.pack(">H", br))

        self.ser.baudrate = 38400

        # todo

    def _send(self, cmd, data=b''):
        l = len(data)
        #print(l)
        o = struct.pack(">BHB", 0x02, cmd, l) + data
        s = sum(o[1:]) & 0xff
        o += struct.pack(">BB", s, 0x03)

        if DEBUG:
            print("sending", o)

        for i in range(len(o)):
            self.ser.write(o[i:i+1])
            time.sleep(0.001)

    def _recv(self):
        stx = self.ser.read(1)
        if stx == b'\x06':
            return True

        if len(stx) == 0:
            if DEBUG:
                print("recv notghin")
            return False

        if not stx == b'\x02':
            if DEBUG:
                print(stx)
            return False
            raise Exception("recvd bad byte")

        cmd = self.ser.read(2)
        cm, = struct.unpack(">H", cmd)
        #print("recv cmd", cmd, " cmd 0x%x" % cm)

        if True: #cm == 0x92:
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
                raise Exception("bad chksum", chsum, c)

            if not etx == 3:
                raise Exception("etx", etx)

#        elif cm == 0x2882:
#            data = self.ser.read(162)
#
#            print(0x2882, len(data), data)
#
#            e = self.ser.read(2)
#            chsum, etx = struct.unpack(">BB", e)
#            print (sum(data), chsum)
#
#            if not etx == b'\x03':
#                print("etx", etx)
#
#        elif cmd == 0x6807:
#            data = self.set.read()

        return cm, data

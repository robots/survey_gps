import struct

class TrimbleXfile:

    data = bytearray(b'\xff' * 0x1000000)
    address_range = []

    def __init__(self, fname = None):
#        if fname is not None:
#            self.load_file(fname)

        self.fin = open(fname, "rb")
        if not self.fin:
            raise Exception("file not found")

        self.hdr = self.fin.read(0x1c)

#    def _add_range(self, r):
#        print("addrange", r, r[1]-r[0], self.address_range)
#
#        found = False
#
#        for i, (start, stop) in enumerate(self.address_range):
#            if r[0] == stop:
#                new_range = (start, r[1])
#                self.address_range[i] = new_range
#                found = True
#                break
#            if r[0] <= start and r[1] >= start and r[1] <= stop:
#                s = start
#                if r[0] < start:
#                    s = r[0]
#                new_range = (s, stop)
#                self.address_range[i] = new_range
#                found = True
#                break
#            if r[1] >= start and r[0] > start and r[0] <= stop:
#                s = stop
#                if r[0] > stop:
#                    s = r[0]
#                new_range = (start, s)
#                self.address_range[i] = new_range
#                found = True
#                break
#
#        if not found:
#            self.address_range.append(r)
#
#        print(self.address_range)

    def next_record(self):

        s = self.fin.read(8)
        if not len(s) == 8:
            return False, False

        xx, l, adr, adr2 = struct.unpack(">HHHH", s)

        adr = adr + (adr2<<16)
        print("%x %x %x %x" % (xx, l, adr, adr+l))

        data = self.fin.read(l)

        if not len(data) == l:
            raise Exception("datalen", len(data), l)
        if l % 2 == 1:
            self.fin.read(1)

            
        return adr, data

#    def load_file(self, fname):
#        with open(fname, "rb") as fin:
#            hdr2 = fin.read(0x1c)
#
#            while True: 
#                x = self.parse_dotxrec(fin)
#                if not x:
#                    break
#                addr, data = x
#
#                for i in range(0, len(data)):
#                    self.data[i+addr] = data[i]
#
#                self._add_range((addr, addr+len(data)))
        

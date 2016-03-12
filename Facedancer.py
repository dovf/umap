# Facedancer.py
#
# Contains class definitions for Facedancer, FacedancerCommand, FacedancerApp,
# and GoodFETMonitorApp.
import struct
from binascii import hexlify


class Facedancer:
    def __init__(self, serialport, verbose=0):
        self.serialport = serialport
        self.verbose = verbose
        self.reset()
        self.monitor_app = GoodFETMonitorApp(self, verbose=self.verbose)
        self.monitor_app.announce_connected()

    def halt(self):
        self.serialport.setRTS(1)
        self.serialport.setDTR(1)

    def reset(self):
        if self.verbose > 0:
            print("Facedancer resetting...")

        self.halt()
        self.serialport.setDTR(0)
        self.readcmd()

        if self.verbose > 0:
            print("Facedancer reset")

    def read(self, n):
        """Read raw bytes."""
        b = self.serialport.read(n)
        if self.verbose > 4:
            print("Facedancer received %s bytes; %s bytes remaining" % (len(b), self.serialport.inWaiting()))
        if self.verbose > 5:
            print("Facedancer Rx:", hexlify(b))
        return b

    def readcmd(self):
        """Read a single command."""

        b = self.read(4)
        app, verb, n = struct.unpack('<BBH', b)

        if n > 0:
            data = self.read(n)
        else:
            data = b''

        if len(data) != n:
            raise ValueError('Facedancer expected %d bytes but received only %d' % (n, len(data)))

        cmd = FacedancerCommand(app, verb, data)

        if self.verbose > 4:
            print("Facedancer Rx command: %s" % cmd)

        return cmd

    def write(self, b):
        """Write raw bytes."""

        if self.verbose > 5:
            print("Facedancer Tx: %s" % hexlify(b))

        self.serialport.write(b)

    def writecmd(self, c):
        """Write a single command."""
        self.write(c.as_bytestring())

        if self.verbose > 4:
            print("Facedancer Tx command: %s" % c)


class FacedancerCommand:
    def __init__(self, app=None, verb=None, data=None):
        self.app = app
        self.verb = verb
        self.data = data

    def __str__(self):
        s = "app 0x%02x, verb 0x%02x, len %d" % (self.app, self.verb, len(self.data))

        if len(self.data) > 0:
            s += ", data %s" % hexlify(self.data)

        return s

    def long_string(self):
        s = "app: %s\nverb: %s\nlen: %s" % (self.app, self.verb, len(self.data))

        if len(self.data) > 0:
            try:
                s += "\n" + self.data.decode("utf-8")
            except UnicodeDecodeError:
                s += "\n" + hexlify(self.data)

        return s

    def as_bytestring(self):
        b = struct.pack('<BBH', self.app, self.verb, len(self.data)) + self.data
        return b


class FacedancerApp:
    app_name = "override this"
    app_num = 0x00

    def __init__(self, device, verbose=0):
        self.device = device
        self.verbose = verbose

        self.init_commands()

        if self.verbose > 0:
            print(self.app_name, "initialized")

    def init_commands(self):
        pass

    def enable(self):
        for i in range(3):
            self.device.writecmd(self.enable_app_cmd)
            self.device.readcmd()

        if self.verbose > 0:
            print(self.app_name, "enabled")


class GoodFETMonitorApp(FacedancerApp):
    app_name = "GoodFET monitor"
    app_num = 0x00

    def read_byte(self, addr):
        d = [addr & 0xff, addr >> 8]
        cmd = FacedancerCommand(0, 2, d)

        self.device.writecmd(cmd)
        resp = self.device.readcmd()

        return struct.unpack('<B', resp.data[0:1])[0]

    def get_infostring(self):
        return struct.pack('<BB', self.read_byte(0xff0), self.read_byte(0xff1))

    def get_clocking(self):
        return struct.pack('<BB', self.read_byte(0x57), self.read_byte(0x56))

    def print_info(self):
        infostring = self.get_infostring()
        clocking = self.get_clocking()

        print("MCU", hexlify(infostring, delim=""))
        print("clocked at", hexlify(clocking, delim=""))

    def list_apps(self):
        cmd = FacedancerCommand(self.app_num, 0x82, b'0x0')
        self.device.writecmd(cmd)

        resp = self.device.readcmd()
        print("build date:", resp.data.decode("utf-8"))

        print("firmware apps:")
        while True:
            resp = self.device.readcmd()
            if len(resp.data) == 0:
                break
            print(resp.data.decode("utf-8"))

    def announce_connected(self):
        cmd = FacedancerCommand(self.app_num, 0xb1, b'')
        self.device.writecmd(cmd)
        self.device.readcmd()

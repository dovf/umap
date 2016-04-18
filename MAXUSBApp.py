# MAXUSBApp.py
#
# Contains class definition for MAXUSBApp.

import sys
import os
import traceback
import struct
import time
from binascii import hexlify
from Facedancer import FacedancerApp, FacedancerCommand
from USBDevice import USBDeviceRequest


class MAXUSBApp(FacedancerApp):
    app_name = "MAXUSB"
    app_num = 0x40

    reg_ep0_fifo = 0x00
    reg_ep1_out_fifo = 0x01
    reg_ep2_in_fifo = 0x02
    reg_ep3_in_fifo = 0x03
    reg_setup_data_fifo = 0x04
    reg_ep0_byte_count = 0x05
    reg_ep1_out_byte_count = 0x06
    reg_ep2_in_byte_count = 0x07
    reg_ep3_in_byte_count = 0x08
    reg_ep_stalls = 0x09
    reg_clr_togs = 0x0a
    reg_endpoint_irq = 0x0b
    reg_endpoint_interrupt_enable = 0x0c
    reg_usb_irq = 0x0d
    reg_usb_interrupt_enable = 0x0e
    reg_usb_control = 0x0f
    reg_cpu_control = 0x10
    reg_pin_control = 0x11
    reg_revision = 0x12
    reg_function_address = 0x13
    reg_io_pins = 0x14

    # bitmask values for reg_endpoint_irq = 0x0b
    is_setup_data_avail = 0x20     # SUDAVIRQ
    is_in3_buffer_avail = 0x10     # IN3BAVIRQ
    is_in2_buffer_avail = 0x08     # IN2BAVIRQ
    is_out1_data_avail = 0x04     # OUT1DAVIRQ
    is_out0_data_avail = 0x02     # OUT0DAVIRQ
    is_in0_buffer_avail = 0x01     # IN0BAVIRQ

    # bitmask values for reg_usb_control = 0x0f
    usb_control_vbgate = 0x40
    usb_control_connect = 0x08

    # bitmask values for reg_pin_control = 0x11
    interrupt_level = 0x08
    full_duplex = 0x10

    def __init__(self, device, logfp, mode, testcase, verbose=0, fuzzer=None):
        FacedancerApp.__init__(self, device, verbose)

        self.connected_device = None
        self.fuzzer = fuzzer
        self.mode = mode
        self.netserver_to_endpoint_sd = 0
        self.netserver_from_endpoint_sd = 0
        self.server_running = False
        self.reply_buffer = ""
        self.testcase = testcase

        self.fplog = 0

        if logfp != 0:
            self.fplog = logfp

        self.fingerprint = []

        self.stop = False
        self.retries = False
        self.enable()

        if verbose > 0:
            rev = self.read_register(self.reg_revision)
            print(self.app_name, "revision", rev)

        # set duplex and negative INT level (from GoodFEDMAXUSB.py)
        self.write_register(self.reg_pin_control, self.full_duplex | self.interrupt_level)

    def get_mutation(self, stage, data=None):
        if self.fuzzer:
            data = {} if data is None else data
            return self.fuzzer.get_mutation(stage=stage, data=data)
        return None

    def init_commands(self):
        self.read_register_cmd = FacedancerCommand(self.app_num, 0x00, b'')
        self.write_register_cmd = FacedancerCommand(self.app_num, 0x00, b'')
        self.enable_app_cmd = FacedancerCommand(self.app_num, 0x10, b'')
        self.ack_cmd = FacedancerCommand(self.app_num, 0x00, b'\x01')

    def read_register(self, reg_num, ack=False):
        if self.verbose > 4:
            print(self.app_name, "reading register 0x%02x" % reg_num)
        mask = 0 if not ack else 1
        self.read_register_cmd.data = struct.pack('<BB', (reg_num << 3) | mask, 0)
        self.device.writecmd(self.read_register_cmd)
        resp = self.device.readcmd()
        reg_val = struct.unpack('<B', resp.data[1:2])[0]
        if self.verbose > 5:
            print(self.app_name, "read register 0x%02x has value 0x%02x" % (reg_num, reg_val))
        return reg_val

    def write_register(self, reg_num, value, ack=False):
        if self.verbose > 4:
            print(self.app_name, "writing register 0x%02x with value 0x%02x" % (reg_num, value))
        mask = 2 if not ack else 3
        self.write_register_cmd.data = struct.pack('<BB', (reg_num << 3) | mask, value)
        self.device.writecmd(self.write_register_cmd)
        self.device.readcmd()

    def get_version(self):
        return self.read_register(self.reg_revision)

    def ack_status_stage(self):
        if self.verbose > 5:
            print(self.app_name, "sending ack!")
        self.device.writecmd(self.ack_cmd)
        self.device.readcmd()

    def connect(self, usb_device):
        self.write_register(self.reg_usb_control, self.usb_control_vbgate | self.usb_control_connect)
        self.connected_device = usb_device
        if self.verbose > 0:
            print(self.app_name, "connected device", self.connected_device.name)

    def disconnect(self):
        self.write_register(self.reg_usb_control, self.usb_control_vbgate)
        if self.verbose > 0:
            if self.connected_device:
                print(self.app_name, "disconnected device", self.connected_device.name)
            else:
                print(self.app_name, 'ERROR: disconnect called when already disconnected')
        self.connected_device = None

    def is_connected(self):
        return self.connected_device is not None

    def clear_irq_bit(self, reg, bit):
        self.write_register(reg, bit)

    def read_bytes(self, reg, n):
        if self.verbose > 5:
            print(self.app_name, "reading", n, "bytes from register", reg)
        data = struct.pack('B', reg << 3) + b'\00' * n
        cmd = FacedancerCommand(self.app_num, 0x00, data)

        self.device.writecmd(cmd)
        resp = self.device.readcmd()
        if self.verbose > 4:
            print(self.app_name, "read %d bytes from register %d", (len(resp.data) - 1, reg))
        return resp.data[1:]

    def write_bytes(self, reg, data):
        data = struct.pack('<B', (reg << 3) | 3) + data
        cmd = FacedancerCommand(self.app_num, 0x00, data)

        self.device.writecmd(cmd)
        self.device.readcmd()  # null response

        if self.verbose > 5:
            print(self.app_name, "wrote %d bytes to register %d", (len(data) - 1, reg))

    # HACK: but given the limitations of the MAX chips, it seems necessary
    def send_on_endpoint(self, ep_num, data):
        if ep_num == 0:
            fifo_reg = self.reg_ep0_fifo
            bc_reg = self.reg_ep0_byte_count
        elif ep_num == 2:
            fifo_reg = self.reg_ep2_in_fifo
            bc_reg = self.reg_ep2_in_byte_count
        elif ep_num == 3:
            fifo_reg = self.reg_ep3_in_fifo
            bc_reg = self.reg_ep3_in_byte_count
        else:
            raise ValueError('endpoint ' + str(ep_num) + ' not supported')

        # FIFO buffer is only 64 bytes, must loop
        while len(data) > 64:
            self.write_bytes(fifo_reg, data[:64])
            self.write_register(bc_reg, 64, ack=True)

            data = data[64:]

        self.write_bytes(fifo_reg, data)
        self.write_register(bc_reg, len(data), ack=True)

        if self.verbose > 3:
            print(self.app_name, "wrote", hexlify(data), "to endpoint", ep_num)

    # HACK: but given the limitations of the MAX chips, it seems necessary
    def read_from_endpoint(self, ep_num):
        if ep_num != 1:
            return b''

        byte_count = self.read_register(self.reg_ep1_out_byte_count)
        if byte_count == 0:
            return b''

        data = self.read_bytes(self.reg_ep1_out_fifo, byte_count)

        if self.verbose > 3:
            print(self.app_name, "read", hexlify(data), "from endpoint", ep_num)

        return data

    def stall_ep0(self):
        if self.verbose > 2:
            print(self.app_name, "stalling endpoint 0")

        self.write_register(self.reg_ep_stalls, 0x23)

    def check_connection_commands(self):
        '''
        :return: whether performed reconnection
        '''
        dev = self.connected_device
        if self.should_disconnect():
            self.disconnect()
            self.clear_disconnect_trigger()
            # wait for reconnection request; no point in returning to service_irqs loop while not connected!
            while not self.should_reconnect():
                self.clear_disconnect_trigger() # be robust to additional disconnect requests
                time.sleep(0.1)
            # now that we received a reconnect request, flow into the handling of it...
        # be robust to reconnection requests, whether received after a disconnect request, or standalone
        # (not sure this is right, might be better to *not* be robust in the face of possible misuse?)
        if self.should_reconnect():
            self.connect(dev)
            self.clear_reconnect_trigger()
            return True
        return False

    def should_reconnect(self):
        if self.fuzzer:
            if os.path.isfile('/tmp/umap_kitty/trigger_reconnect'):
                return True
        return False

    def clear_reconnect_trigger(self):
        trigger = '/tmp/umap_kitty/trigger_reconnect'
        if os.path.isfile(trigger):
            os.remove(trigger)

    def should_disconnect(self):
        if self.fuzzer:
            if os.path.isfile('/tmp/umap_kitty/trigger_disconnect'):
                return True
        return False

    def clear_disconnect_trigger(self):
        trigger = '/tmp/umap_kitty/trigger_disconnect'
        if os.path.isfile(trigger):
            os.remove(trigger)

    def send_heartbeat(self):
        heartbeat_file = '/tmp/umap_kitty/heartbeat'
        with open(heartbeat_file, 'a'):
            os.utime(heartbeat_file, None)

    def service_irqs(self):
        count = 0
        tmp_irq = 0

        while not self.stop:
            irq = self.read_register(self.reg_endpoint_irq)

            if irq == tmp_irq:
                count += 1
            else:
                self.send_heartbeat()
                count = 0

            if count == 10000 and self.mode == 2:  # This needs to be configurable
                self.stop = True
                if self.fplog:
                    self.fplog.write("\n")
                if self.verbose > 0:
                    print('count == 10000 and self.mode == 2')
                return

            if count == 2000 and (self.mode == 3 or self.mode == 1 or self.mode == 4):  # This needs to be configurable
                self.stop = True

                if len(self.fingerprint) == 0:
                    print ("\n*** No response from host - check if the host is still functioning correctly ***\n")
                    self.disconnect()
                    sys.exit()

                self.disconnect()

                if self.fplog:
                    self.fplog.write("\n")
                if self.verbose > 0:
                    print('count == 2000 and (self.mode(%s) == 3, 1 or 4)' % (self.mode))
                return

            if self.verbose > 4:
                print(self.app_name, "read endpoint irq: 0x%02x" % irq)

            if self.verbose > 3:
                if irq & ~ (
                    self.is_in0_buffer_avail |
                    self.is_in2_buffer_avail |
                    self.is_in3_buffer_avail
                ):
                    print(self.app_name, "notable irq: 0x%02x" % irq)

            if irq & self.is_setup_data_avail:
                self.clear_irq_bit(self.reg_endpoint_irq, self.is_setup_data_avail)

                b = self.read_bytes(self.reg_setup_data_fifo, 8)
                req = USBDeviceRequest(b)
                self.connected_device.handle_request(req)

            if irq & self.is_out1_data_avail:
                data = self.read_from_endpoint(1)
                if data:
                    self.connected_device.handle_data_available(1, data)
                self.clear_irq_bit(self.reg_endpoint_irq, self.is_out1_data_avail)

            if irq & self.is_in2_buffer_avail:
                try:
                    self.connected_device.handle_buffer_available(2)
                except:
                    traceback.print_exc()
                    print('umap ignored the exception for some reason... will need to address that later on')
                    raise

            if irq & self.is_in3_buffer_avail:
                try:
                    self.connected_device.handle_buffer_available(3)
                except:
                    traceback.print_exc()
                    print('umap ignored the exception for some reason... will need to address that later on')
                    raise
            tmp_irq = irq
            if self.check_connection_commands():
                count = 0
        self.disconnect()

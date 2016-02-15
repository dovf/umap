# USBPrinter.py
#
# Contains class definitions to implement a USB printer device.
import time
from struct import pack

from USB import *
from USBDevice import *
from USBConfiguration import *
from USBInterface import *
from USBEndpoint import *
from USBClass import *
from util import *


class USBPrinterClass(USBClass):
    name = "USB printer class"

    def setup_request_handlers(self):
        self.local_handlers = {
            0x00: ('get_device_id_response', self.handle_get_device_id_request),
        }
        self.request_handlers = {
            x: self.handle_all for x in self.local_handlers
        }

    def handle_all(self, req):
        stage, handler = self.local_handlers[req.request]
        response = self.get_mutation(stage=stage)
        if response is None:
            response = handler(req)
        self.app.send_on_endpoint(0, response)
        self.supported()

    def handle_get_device_id_request(self, req):
        device_id_dict = {
            'MFG': 'Hewlett-Packard',
            'CMD': 'PJL,PML,PCLXL,POSTSCRIPT,PCL',
            'MDL': 'HP Color LaserJet CP1515n',
            'CLS': 'PRINTER',
            'DES': 'Hewlett-Packard Color LaserJet CP1515n',
            'MEM': 'MEM=55MB',
            'COMMENT': 'RES=600x8',
        }
        device_id = ';'.join(k + ':' + v for k, v in device_id_dict.items())
        device_id += ';'
        length = pack('>H', len(device_id))
        response = length + str.encode(device_id)
        return response


class USBPrinterInterface(USBInterface):
    name = "USB printer interface"

    def __init__(self, int_num, maxusb_app, usbclass, sub, proto, verbose=0):
        self.maxusb_app = maxusb_app
        self.filename = time.strftime("%Y%m%d%H%M%S", time.localtime())
        self.filename += ".pcl"
        self.writing = False

        descriptors = {}

        endpoints0 = [
            USBEndpoint(
                maxusb_app=maxusb_app,
                number=1,          # endpoint address
                direction=USBEndpoint.direction_out,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=16384,      # max packet size
                interval=0xff,          # polling interval, see USB 2.0 spec Table 9-13
                handler=self.handle_data_available    # handler function
            ),
            USBEndpoint(
                maxusb_app=maxusb_app,
                number=0x81,          # endpoint address
                direction=USBEndpoint.direction_in,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=16384,      # max packet size
                interval=0,          # polling interval, see USB 2.0 spec Table 9-13
                handler=None        # handler function
            )
        ]

        endpoints1 = [
            USBEndpoint(
                maxusb_app=maxusb_app,
                number=0x0b,          # endpoint address
                direction=USBEndpoint.direction_out,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=16384,      # max packet size
                interval=0xff,          # polling interval, see USB 2.0 spec Table 9-13
                handler=self.handle_data_available    # handler function
            ),
            USBEndpoint(
                maxusb_app=maxusb_app,
                number=0x8b,          # endpoint address
                direction=USBEndpoint.direction_in,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=16384,      # max packet size
                interval=0,          # polling interval, see USB 2.0 spec Table 9-13
                handler=None        # handler function
            )
        ]
        if int_num == 0:
            endpoints = endpoints0
        if int_num == 1:
            endpoints = endpoints1

        # TODO: un-hardcode string index (last arg before "verbose")
        super(USBPrinterInterface, self).__init__(
                maxusb_app=maxusb_app,
                interface_number=int_num,          # interface number
                interface_alternate=0,          # alternate setting
                interface_class=usbclass,     # interface class
                interface_subclass=sub,          # subclass
                interface_protocol=proto,       # protocol
                interface_string_index=0,          # string index
                verbose=verbose,
                endpoints=endpoints,
                descriptors=descriptors
        )

        self.device_class = USBPrinterClass(maxusb_app, verbose)
        self.device_class.set_interface(self)

        self.is_write_in_progress = False
        self.write_cbw = None
        self.write_base_lba = 0
        self.write_length = 0
        self.write_data = b''

    def handle_data_available(self, data):
        if not self.writing:
            print ("Writing PCL file: %s" % self.filename)

        with open(self.filename, "ab") as out_file:
            self.writing = True
            out_file.write(data)

        text_buffer = ''.join(chr(c) for c in data)

        if 'EOJ\n' in text_buffer:
            print ("File write complete")
            out_file.close()
            self.maxusb_app.stop = True


class USBPrinterDevice(USBDevice):
    name = "USB printer device"

    def __init__(self, maxusb_app, vid, pid, rev, usbclass, subclass, proto, verbose=0):
        interfaces = [
            USBPrinterInterface(0, maxusb_app, usbclass, subclass, proto, verbose=verbose),
            USBPrinterInterface(1, maxusb_app, 0xff, 1, 1, verbose=verbose),
        ]
        config = USBConfiguration(
                maxusb_app=maxusb_app,
                configuration_index=1,
                configuration_string="Printer",
                interfaces=interfaces
        )
        super(USBPrinterDevice, self).__init__(
                maxusb_app=maxusb_app,
                device_class=0,
                device_subclass=0,
                protocol_rel_num=0,
                max_packet_size_ep0=64,
                vendor_id=vid,
                product_id=pid,
                device_rev=rev,
                manufacturer_string="Hewlett-Packard",
                product_string="HP Color LaserJet CP1515n",
                serial_number_string="00CNC2618971",
                configurations=[config],
                verbose=verbose
        )

    def disconnect(self):
        USBDevice.disconnect(self)

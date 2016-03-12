# USBVendorSpecific.py
#

from USBClass import USBClass
from USBDevice import USBDevice
from USBConfiguration import USBConfiguration
from USBInterface import USBInterface
from USBEndpoint import USBEndpoint
from USBVendor import *


class USBVendorVendor(USBVendor):
    name = "USB vendor"

    def setup_request_handlers(self):
        self.request_handlers = {
             0: self.handle_reset_request
        }

    def handle_reset_request(self, req):
        if self.verbose > 0:
            print(self.name, "received reset request")

        self.device.app.send_on_endpoint(0, b'')


class USBVendorClass(USBClass):
    name = "USB Vendor class"

    def __init__(self, app):

        self.app = app
        self.setup_request_handlers()

    def setup_request_handlers(self):
        self.request_handlers = {
            0x01: self.handle_get_report
        }

    def handle_get_report(self, req):
        response = b''
        self.app.send_on_endpoint(0, response)


class USBVendorInterface(USBInterface):
    name = "USB Vendor interface"

    def __init__(self, app, verbose=0):
        descriptors = {}
        endpoints = [
            USBEndpoint(
                app,
                1,          # endpoint number
                USBEndpoint.direction_out,
                USBEndpoint.transfer_type_bulk,
                USBEndpoint.sync_type_none,
                USBEndpoint.usage_type_data,
                16384,      # max packet size
                0,         # polling interval, see USB 2.0 spec Table 9-13
                self.handle_data_available    # handler function
            ),
            USBEndpoint(
                app,
                2,          # endpoint number
                USBEndpoint.direction_in,
                USBEndpoint.transfer_type_bulk,
                USBEndpoint.sync_type_none,
                USBEndpoint.usage_type_data,
                16384,      # max packet size
                0,         # polling interval, see USB 2.0 spec Table 9-13
                None    # handler function
            ),
            USBEndpoint(
                app,
                3,          # endpoint number
                USBEndpoint.direction_in,
                USBEndpoint.transfer_type_interrupt,
                USBEndpoint.sync_type_none,
                USBEndpoint.usage_type_data,
                16384,      # max packet size
                8,         # polling interval, see USB 2.0 spec Table 9-13
                self.handle_buffer_available    # handler function
            ),
        ]

        # TODO: un-hardcode string index (last arg before "verbose")
        super(USBVendorInterface, self).__init__(
                app=app,
                interface_number=0,          # interface number
                interface_alternate=0,          # alternate setting
                interface_class=0xff,       # 3 interface class
                interface_subclass=0xff,          # 0 subclass
                interface_protocol=0xff,          # 0 protocol
                interface_string_index=0,          # string index
                verbose=verbose,
                endpoints=endpoints,
                descriptors=descriptors
        )

        self.device_class = USBVendorClass(app)
        self.device_class.interface = self

    def handle_data_available(self, data):
        return

    def handle_buffer_available(self):
        return


class USBVendorDevice(USBDevice):
    name = "USB Vendor device"

    def __init__(self, app, vid, pid, rev, verbose=0, **kwargs):
        interface = USBVendorInterface(app=app, verbose=verbose)
        config = USBConfiguration(
                app=app,
                configuration_index=1,
                configuration_string="Vendor device",
                interfaces=[interface]
        )

        super(USBVendorDevice, self).__init__(
            app=app,
            device_class=0xff,
            device_subclass=0xff,
            protocol_rel_num=0xff,
            max_packet_size_ep0=64,
            vendor_id=vid,
            product_id=pid,
            device_rev=rev,
            manufacturer_string="Vendor",
            product_string="Product",
            serial_number_string="00000000",
            configurations=[config],
            verbose=verbose
        )

        self.device_vendor = USBVendorVendor()
        self.device_vendor.set_device(self)

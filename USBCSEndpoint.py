# USBCSEndpoint.py
#
# Contains class definition for USBCSEndpoint.
from struct import pack, unpack
from USBBase import USBBaseActor
from devices.wrappers import mutable


class USBCSEndpoint(USBBaseActor):

    def __init__(self, app, cs_config, verbose=0):
        super(USBCSEndpoint, self).__init__(app, verbose)
        self.cs_config = cs_config
        self.number = self.cs_config[1]
        self.interface = None
        self.device_class = None
        self.request_handlers = {
            1: self.handle_clear_feature_request
        }

    def handle_clear_feature_request(self, req):
        if self.app.mode != 2:
            # print("received CLEAR_FEATURE request for endpoint", self.number,
            #        "with value", req.value)
            self.interface.configuration.device.app.send_on_endpoint(0, b'')

    def set_interface(self, interface):
        self.interface = interface

    # see Table 9-13 of USB 2.0 spec (pdf page 297)
    @mutable('usbcsendpoint_descriptor')
    def get_descriptor(self):
        if self.cs_config[0] == 0x01:  # EP_GENERAL
            bLength = 7
            bDescriptorType = 37  # CS_ENDPOINT
            bDescriptorSubtype = 0x01  # EP_GENERAL
            bmAttributes, bLockDelayUnits, wLockDelay = unpack('<BBB', self.cs_config[2:5])

        d = pack(
            '<BBBBBH',
            bLength,
            bDescriptorType,
            bDescriptorSubtype,
            bmAttributes,
            bLockDelayUnits,
            wLockDelay,
        )

        return d


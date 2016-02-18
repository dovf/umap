# USBEndpoint.py
#
# Contains class definition for USBEndpoint.
from struct import pack
from USBBase import USBBaseActor
from devices.wrappers import mutable


class USBEndpoint(USBBaseActor):
    direction_out = 0x00
    direction_in = 0x01

    transfer_type_control = 0x00
    transfer_type_isochronous = 0x01
    transfer_type_bulk = 0x02
    transfer_type_interrupt = 0x03

    sync_type_none = 0x00
    sync_type_async = 0x01
    sync_type_adaptive = 0x02
    sync_type_synchronous = 0x03

    usage_type_data = 0x00
    usage_type_feedback = 0x01
    usage_type_implicit_feedback = 0x02

    def __init__(
            self, app, number, direction, transfer_type, sync_type,
            usage_type, max_packet_size, interval, handler, verbose=0):
        '''
        :type app: :class:`~MAXUSBApp.MAXUSBApp`
        :param app: application
        :param number: endpoint number
        :param direction: endpoint direction (direction_in/direction_out)
        :param transfer_type: one of USBEndpoint.transfer_type\*
        :param sync_type: one of USBEndpoint.sync_type\*
        :param usage_type: on of USBEndpoint.usage_type\*
        :param max_packet_size: maximum size of a packet
        :param interval: TODO
        :type handler:
            func(data) -> None if direction is out,
            func() -> None if direction is IN
        :param handler: interrupt handler for the endpoint

        .. note:: OUT endpoint is 1, IN endpoint is either 2 or 3
        '''
        super().__init__(app, verbose)
        self.app = app
        self.number = number
        self.direction = direction
        self.transfer_type = transfer_type
        self.sync_type = sync_type
        self.usage_type = usage_type
        self.max_packet_size = max_packet_size
        self.interval = interval
        self.handler = handler
        self.interface = None

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
    @mutable('endpoint_descriptor')
    def get_descriptor(self):
        address = (self.number & 0x0f) | (self.direction << 7)
        attributes = (
            (self.transfer_type & 0x03) |
            ((self.sync_type & 0x03) << 2) |
            ((self.usage_type & 0x03) << 4)
        )
        bLength = 7
        bDescriptorType = 5

        d = pack(
            '<BBBBHB',
            bLength,
            bDescriptorType,
            address,
            attributes,
            self.max_packet_size,
            self.interval
        )
        return d

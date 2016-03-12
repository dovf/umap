# USBClass.py
#
# Contains class definition for USBClass, intended as a base class (in the OO
# sense) for implementing device classes (in the USB sense), eg, HID devices,
# mass storage devices.
from USBBase import USBBaseActor


class USBClass(USBBaseActor):
    name = "generic USB device class"

    # maps bRequest to handler function
    request_handlers = {}

    def __init__(self, app, verbose=0):
        super(USBClass, self).__init__(app, verbose)
        self.interface = None
        self.setup_request_handlers()

    def set_interface(self, interface):
        self.interface = interface

    def setup_request_handlers(self):
        self.setup_local_handlers()
        self.request_handlers = {
            x: self.handle_all for x in self.local_handlers
        }

    def setup_local_handlers(self):
        self.local_handlers = {}

    def handle_all(self, req):
        handler = self.local_handlers[req.request]
        response = handler(req)
        if response is not None:
            self.app.send_on_endpoint(0, response)
        self.supported()

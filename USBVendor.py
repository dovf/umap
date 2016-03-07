# USBVendor.py
#
# Contains class definition for USBVendor, intended as a base class (in the OO
# sense) for implementing device vendors.
from USBBase import USBBaseActor


class USBVendor(USBBaseActor):
    name = "generic USB device vendor"

    # maps bRequest to handler function
    request_handlers = {}

    def __init__(self, app, verbose=0):
        super().__init__(app, verbose)
        self.device = None
        self.setup_request_handlers()

    def set_device(self, device):
        self.device = device

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

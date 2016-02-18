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
        super().__init__(app, verbose)
        self.interface = None
        self.setup_request_handlers()

    def set_interface(self, interface):
        self.interface = interface

    def setup_request_handlers(self):
        """To be overridden for subclasses to modify self.class_request_handlers"""
        pass

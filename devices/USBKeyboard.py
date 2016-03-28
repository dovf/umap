# USBKeyboard.py
#
# Contains class definitions to implement a USB keyboard.

from USB import USB
from USBClass import USBClass
from USBDevice import USBDevice
from USBConfiguration import USBConfiguration
from USBInterface import USBInterface
from USBEndpoint import USBEndpoint
from fuzzing.wrappers import mutable
import struct


class Requests(object):
    GET_REPORT = 0x01  # Mandatory
    GET_IDLE = 0x02
    GET_PROTOCOL = 0x03  # Ignored - only for boot device
    SET_REPORT = 0x09
    SET_IDLE = 0x0A
    SET_PROTOCOL = 0x0B  # Ignored - only for boot device


class USBKeyboardClass(USBClass):
    name = "USB Keyboard class"

    def setup_local_handlers(self):
        self.local_handlers = {
            Requests.GET_REPORT: self.handle_get_report,
            Requests.GET_IDLE: self.handle_get_idle,
            Requests.SET_REPORT: self.handle_set_report,
            Requests.SET_IDLE: self.handle_set_idle,
        }

    @mutable('hid_get_report_response')
    def handle_get_report(self, req):
        response = b'\xff' * req.length
        return response

    @mutable('hid_get_idle_response')
    def handle_get_idle(self, req):
        return b''

    @mutable('hid_set_report_response')
    def handle_set_report(self, req):
        return b''

    @mutable('hid_set_idle_response')
    def handle_set_idle(self, req):
        return b''


class USBKeyboardInterface(USBInterface):
    name = "USB keyboard interface"

    def __init__(self, app, verbose=0):
        descriptors = {
            USB.desc_type_hid: self.get_hid_descriptor,
            USB.desc_type_report: self.get_report_descriptor
        }

        endpoint = USBEndpoint(
            app=app,
            number=2,
            direction=USBEndpoint.direction_in,
            transfer_type=USBEndpoint.transfer_type_interrupt,
            sync_type=USBEndpoint.sync_type_none,
            usage_type=USBEndpoint.usage_type_data,
            max_packet_size=0x40,
            interval=10,
            handler=self.handle_buffer_available
        )

        # TODO: un-hardcode string index (last arg before "verbose")
        super(USBKeyboardInterface, self).__init__(
            app=app,
            interface_number=0,
            interface_alternate=0,
            interface_class=USBClass.HID,
            interface_subclass=0,
            interface_protocol=0,
            interface_string_index=0,
            verbose=verbose,
            endpoints=[endpoint],
            descriptors=descriptors
        )

        self.device_class = USBKeyboardClass(app, verbose)
        self.device_class.set_interface(self)

        empty_preamble = [0x00] * 10
        text = [0x0f, 0x00, 0x16, 0x00, 0x28, 0x00]
        # text = []

        self.keys = [chr(x) for x in empty_preamble + text]
        self.call_count = 0

    @mutable('hid_descriptor')
    def get_hid_descriptor(self, *args, **kwargs):
        report_descriptor = self.get_report_descriptor()
        bDescriptorType = b'\x21'  # HID
        bcdHID = b'\x10\x01'
        bCountryCode = b'\x00'
        bNumDescriptors = b'\x01'
        bDescriptorType2 = b'\x22'  # REPORT
        desclen = len(report_descriptor)
        wDescriptorLength = struct.pack('<H', desclen)
        hid_descriptor = (
            bDescriptorType +
            bcdHID +
            bCountryCode +
            bNumDescriptors +
            bDescriptorType2 +
            wDescriptorLength
        )
        bLength = struct.pack('<B', len(hid_descriptor) + 1)
        hid_descriptor = bLength + hid_descriptor
        return hid_descriptor

    @mutable('hid_report_descriptor')
    def get_report_descriptor(self, *args, **kwargs):
        usage_page_generic_desktop_controls = b'\x05\x01'
        # usage_page_generic_desktop_controls = b'\xb1\x01'
        usage_keyboard = b'\x09\x06'
        collection_application = b'\xA1\x01'
        usage_page_keyboard = b'\x05\x07'
        usage_minimum1 = b'\x19\xE0'
        usage_maximum1 = b'\x29\xE7'
        logical_minimum1 = b'\x15\x00'
        logical_maximum1 = b'\x25\x01'
        report_size1 = b'\x75\x01'
        report_count1 = b'\x95\x08'
        input_data_variable_absolute_bitfield = b'\x81\x02'
        report_count2 = b'\x95\x01'
        report_size2 = b'\x75\x08'
        input_constant_array_absolute_bitfield = b'\x81\x01'
        usage_minimum2 = b'\x19\x00'
        usage_maximum2 = b'\x29\x65'
        logical_minimum2 = b'\x15\x00'
        logical_maximum2 = b'\x25\x65'
        report_size3 = b'\x75\x08'
        report_count3 = b'\x95\x01'
        input_data_array_absolute_bitfield = b'\x81\x00'
        end_collection = b'\xc0'

        report_descriptor = (
            usage_page_generic_desktop_controls +
            usage_keyboard +
            collection_application +
            usage_page_keyboard +
            usage_minimum1 +
            usage_maximum1 +
            logical_minimum1 +
            logical_maximum1 +
            report_size1 +
            report_count1 +
            input_data_variable_absolute_bitfield +
            report_count2 +
            report_size2 +
            input_constant_array_absolute_bitfield +
            usage_minimum2 +
            usage_maximum2 +
            logical_minimum2 +
            logical_maximum2 +
            report_size3 +
            report_count3 +
            input_data_array_absolute_bitfield +
            end_collection
        )
        return report_descriptor

    def handle_buffer_available(self):
        #
        # this is really ugly, but sometimes the host expects
        # (during initialization) to get the report on ep0 and
        # ignores the actual ep (2 in this case), we'll just
        # wait for a little bit... (see section 7.2.1 in HID spec)
        #
        if self.call_count > 100:
            self.supported()
            if self.keys:
                letter = self.keys.pop(0)
                self.type_letter(letter)
        else:
            self.call_count += 1

    def type_letter(self, letter, modifiers=0):
        data = struct.pack('<BBB', 0, 0, ord(letter))
        self.logger.verbose(self.name, "sending keypress 0x%02x" % ord(letter))
        self.configuration.device.app.send_on_endpoint(2, data)


class USBKeyboardDevice(USBDevice):
    name = "USB keyboard device"

    def __init__(self, app, vid, pid, rev, verbose=0, **kwargs):
        interface = USBKeyboardInterface(app, verbose=verbose)
        config = USBConfiguration(
            app=app,
            configuration_index=1,
            configuration_string="Emulated Keyboard",
            interfaces=[interface]
        )
        super(USBKeyboardDevice, self).__init__(
            app=app,
            device_class=USBClass.Unspecified,
            device_subclass=0,
            protocol_rel_num=0,
            max_packet_size_ep0=64,
            vendor_id=vid,
            product_id=pid,
            device_rev=rev,
            manufacturer_string="Dell",
            product_string="Dell USB Entry Keyboard",
            serial_number_string="00001",
            configurations=[config],
            descriptors={},
            verbose=verbose
        )

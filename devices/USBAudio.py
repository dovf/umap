# USBAudio.py
#
# Contains class definitions to implement a USB Audio device.

from USB import *
from USBDevice import *
from USBConfiguration import *
from USBInterface import *
from USBCSInterface import *
from USBEndpoint import *
from USBCSEndpoint import *
from .wrappers import mutable


class USBAudioClass(USBClass):
    name = "USB Audio class"

    def setup_request_handlers(self):
        self.local_responses = {
            0x0a: ('audio_set_idle_response', b''),
            0x83: ('audio_get_max_response', b'\xf0\xff'),
            0x82: ('audio_get_min_response', b'\xa0\xe0'),
            0x84: ('audio_get_res_response', b'\x30\x00'),
            0x81: ('audio_get_cur_response', b''),
            0x04: ('audio_set_res_response', b''),
            0x01: ('audio_set_cur_response', b'')
        }
        self.request_handlers = {
            x: self.handle_all for x in self.local_responses
        }

    def handle_all(self, req):
        stage, default_response = self.local_responses[req.request]
        response = self.get_mutation(stage=stage)
        if response is None:
            response = default_response
        self.app.send_on_endpoint(0, response)
        self.supported()


class USBAudioInterface(USBInterface):
    name = "USB audio interface"

    def __init__(self, int_num, app, usbclass, sub, proto, verbose=0):
        descriptors = {
            USB.desc_type_hid: self.get_hid_descriptor,
            USB.desc_type_report: self.get_report_descriptor
        }

        wTotalLength = 0x0047
        bInCollection = 0x02
        baInterfaceNr1 = 0x01
        baInterfaceNr2 = 0x02

        cs_config1 = [
            0x01,            # HEADER
            0x0001,          # bcdADC
            wTotalLength,    # wTotalLength
            bInCollection,   # bInCollection
            baInterfaceNr1,  # baInterfaceNr1
            baInterfaceNr2   # baInterfaceNr2
        ]

        bTerminalID = 0x01
        wTerminalType = 0x0101
        bAssocTerminal = 0x0
        bNrChannel = 0x02
        wChannelConfig = 0x0002

        cs_config2 = [
            0x02,            # INPUT_TERMINAL
            bTerminalID,     # bTerminalID
            wTerminalType,   # wTerminalType
            bAssocTerminal,  # bAssocTerminal
            bNrChannel,      # bNrChannel
            wChannelConfig,  # wChannelConfig
            0,          # iChannelNames
            0           # iTerminal
        ]

        cs_config3 = [
            0x02,       # INPUT_TERMINAL
            0x02,       # bTerminalID
            0x0201,     # wTerminalType
            0,          # bAssocTerminal
            0x01,       # bNrChannel
            0x0001,     # wChannelConfig
            0,          # iChannelNames
            0           # iTerminal
        ]

        bSourceID = 0x09

        cs_config4 = [
            0x03,       # OUTPUT_TERMINAL
            0x06,       # bTerminalID
            0x0301,     # wTerminalType
            0,          # bAssocTerminal
            bSourceID,  # bSourceID
            0           # iTerminal
        ]

        cs_config5 = [
            0x03,       # OUTPUT_TERMINAL
            0x07,       # bTerminalID
            0x0101,     # wTerminalType
            0,          # bAssocTerminal
            0x0a,       # bSourceID
            0           # iTerminal
        ]

        bUnitID = 0x09
        bSourceID = 0x01
        bControlSize = 0x01
        bmaControls0 = 0x01
        bmaControls1 = 0x02
        bmaControls2 = 0x02

        cs_config6 = [
            0x06,           # FEATURE_UNIT
            bUnitID,        # bUnitID
            bSourceID,      # bSourceID
            bControlSize,   # bControlSize
            bmaControls0,   # bmaControls0
            bmaControls1,   # bmaControls1
            bmaControls2,   # bmaControls2
            0               # iFeature
        ]

        cs_config7 = [
            0x06,       # FEATURE_UNIT
            0x0a,       # bUnitID
            0x02,       # bSourceID
            0x01,       # bControlSize
            0x43,       # bmaControls0
            0x00,       # bmaControls1
            0x00,       # bmaControls2
            0           # iFeature
        ]

        cs_interfaces0 = [
            USBCSInterface(app, cs_config1, 1, 1, 0),
            USBCSInterface(app, cs_config2, 1, 1, 0),
            USBCSInterface(app, cs_config3, 1, 1, 0),
            USBCSInterface(app, cs_config4, 1, 1, 0),
            USBCSInterface(app, cs_config5, 1, 1, 0),
            USBCSInterface(app, cs_config6, 1, 1, 0),
            USBCSInterface(app, cs_config7, 1, 1, 0)
        ]

        # cs_config8 = [
        #     0x01,       # AS_GENERAL
        #     0x01,       # bTerminalLink
        #     0x01,       # bDelay
        #     0x0001      # wFormatTag
        # ]

        # cs_config9 = [
        #     0x02,       # FORMAT_TYPE
        #     0x01,       # bFormatType
        #     0x02,       # bNrChannels
        #     0x02,       # bSubframeSize
        #     0x10,       # bBitResolution
        #     0x02,       # SamFreqType
        #     0x80bb00,    # tSamFreq1
        #     0x44ac00    # tSamFreq2
        # ]

        cs_interfaces1 = []
        cs_interfaces2 = []
        cs_interfaces3 = []

        # ep_cs_config1 = [
        #     0x01,       # EP_GENERAL
        #     0x01,       # Endpoint number
        #     0x01,       # bmAttributes
        #     0x01,       # bLockDelayUnits
        #     0x0001,     # wLockeDelay
        # ]

        endpoints0 = [
            USBEndpoint(
                app=app,
                number=2,
                direction=USBEndpoint.direction_in,
                transfer_type=USBEndpoint.transfer_type_interrupt,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=0x0400,
                interval=0x02,
                handler=self.audio_ep2_buffer_available
            )
        ]

        if int_num == 3:
            endpoints = endpoints0
        else:
            endpoints = []

        if int_num == 0:
            cs_interfaces = cs_interfaces0
        if int_num == 1:
            cs_interfaces = cs_interfaces1
        if int_num == 2:
            cs_interfaces = cs_interfaces2
        if int_num == 3:
            cs_interfaces = cs_interfaces3

        # if self.int_num == 1:
        #     endpoints = endpoints1

        # TODO: un-hardcode string index (last arg before "verbose")
        super(USBAudioInterface, self).__init__(
            app=app,
            interface_number=int_num,          # interface number
            interface_alternate=0,          # alternate setting
            interface_class=usbclass,          # 3 interface class
            interface_subclass=sub,          # 0 subclass
            interface_protocol=proto,          # 0 protocol
            interface_string_index=0,          # string index
            verbose=verbose,
            endpoints=endpoints,
            descriptors=descriptors,
            cs_interfaces=cs_interfaces
        )

        self.device_class = USBAudioClass(app)
        self.device_class.set_interface(self)

    @mutable('audio_ep2_buffer_available')
    def audio_ep2_buffer_available(self):
        if self.verbose > 0:
            print(self.name, "handling buffer available on ep2")
        return self.app.send_on_endpoint(2, b'\x00\x00\x00')

    @mutable('audio_hid_descriptor')
    def get_hid_descriptor(self, *args, **kwargs):
        return b'\x09\x21\x10\x01\x00\x01\x22\x2b\x00'

    @mutable('audio_report_descriptor')
    def get_report_descriptor(self, *args, **kwargs):
        return(
            b'\x05\x0C\x09\x01\xA1\x01\x15\x00\x25\x01\x09\xE9\x09\xEA\x75' +
            b'\x01\x95\x02\x81\x02\x09\xE2\x09\x00\x81\x06\x05\x0B\x09\x20' +
            b'\x95\x01\x81\x42\x05\x0C\x09\x00\x95\x03\x81\x02\x26\xFF\x00' +
            b'\x09\x00\x75\x08\x95\x03\x81\x02\x09\x00\x95\x04\x91\x02\xC0'
            )


class USBAudioDevice(USBDevice):
    name = "USB audio device"

    def __init__(self, app, vid, pid, rev, verbose=0, **kwargs):
        interface0 = USBAudioInterface(0, app, 0x01, 0x01, 0x00, verbose=verbose)
        interface1 = USBAudioInterface(1, app, 0x01, 0x02, 0x00, verbose=verbose)
        interface2 = USBAudioInterface(2, app, 0x01, 0x02, 0x00, verbose=verbose)
        interface3 = USBAudioInterface(3, app, 0x03, 0x00, 0x00, verbose=verbose)

        if vid == 0x1111:
            vid = 0x041e
        if pid == 0x2222:
            pid = 0x0402
        if rev == 0x3333:
            rev = 0x0100

        config = USBConfiguration(
            app=app,
            configuration_index=1,
            configuration_string="Emulated Audio",
            interfaces=[
                interface0,
                interface1,
                interface2,
                interface3
            ]
        )

        super(USBAudioDevice, self).__init__(
            app=app,
            device_class=0,
            device_subclass=0,
            protocol_rel_num=0,
            max_packet_size_ep0=64,
            vendor_id=vid,
            product_id=pid,
            device_rev=rev,
            manufacturer_string="Creative Technology Ltd.",
            product_string="Creative HS-720 Headset",
            serial_number_string="",
            configurations=[config],
            descriptors={},
            verbose=verbose
        )

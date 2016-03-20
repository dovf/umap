# USBDevice.py
#
# Contains class definitions for USBDevice and USBDeviceRequest.

import traceback
import struct
from USB import USB
from USBBase import USBBaseActor
from devices.wrappers import mutable


class USBDevice(USBBaseActor):
    name = "generic device"

    def __init__(
            self, app, device_class, device_subclass,
            protocol_rel_num, max_packet_size_ep0, vendor_id, product_id,
            device_rev, manufacturer_string, product_string,
            serial_number_string, configurations=[], descriptors={},
            verbose=0):
        super(USBDevice, self).__init__(app, verbose)
        self.supported_device_class_trigger = False
        self.supported_device_class_count = 0

        self.strings = []

        self.usb_spec_version = 0x0002
        self.device_class = device_class
        self.device_subclass = device_subclass
        self.protocol_rel_num = protocol_rel_num
        self.max_packet_size_ep0 = max_packet_size_ep0
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device_rev = device_rev

        self.manufacturer_string_id = self.get_string_id(manufacturer_string)
        self.product_string_id = self.get_string_id(product_string)
        self.serial_number_string_id = self.get_string_id(serial_number_string)

        # maps from USB.desc_type_* to bytearray OR callable
        self.descriptors = descriptors
        self.descriptors[USB.desc_type_device] = self.get_descriptor
        self.descriptors[USB.desc_type_configuration] = self.get_configuration_descriptor
        self.descriptors[USB.desc_type_string] = self.handle_get_string_descriptor_request
        self.descriptors[USB.desc_type_hub] = self.handle_get_hub_descriptor_request
        self.descriptors[USB.desc_type_device_qualifier] = self.get_device_qualifier_descriptor

        self.config_num = -1
        self.configuration = None
        self.configurations = configurations

        for c in self.configurations:
            csi = self.get_string_id(c.configuration_string)
            c.set_configuration_string_index(csi)
            c.set_device(self)

        self.state = USB.state_detached
        self.ready = False

        self.address = 0

        self.setup_request_handlers()

    def get_string_id(self, s):
        try:
            i = self.strings.index(s)
        except ValueError:
            # string descriptors start at index 1
            self.strings.append(s)
            i = len(self.strings)
        return i

    def setup_request_handlers(self):
        # see table 9-4 of USB 2.0 spec, page 279
        self.request_handlers = {
            0: self.handle_get_status_request,
            1: self.handle_clear_feature_request,
            3: self.handle_set_feature_request,
            5: self.handle_set_address_request,
            6: self.handle_get_descriptor_request,
            7: self.handle_set_descriptor_request,
            8: self.handle_get_configuration_request,
            9: self.handle_set_configuration_request,
            10: self.handle_get_interface_request,
            11: self.handle_set_interface_request,
            12: self.handle_synch_frame_request
        }

    def connect(self):
        self.app.connect(self)

        # skipping USB.state_attached may not be strictly correct (9.1.1.{1,2})
        self.state = USB.state_powered

    def disconnect(self):
        if self.app.is_connected():
            self.app.disconnect()
        self.app.server_running = False

        if self.app.netserver_to_endpoint_sd:
            self.app.netserver_to_endpoint_sd.close()

        if self.app.netserver_from_endpoint_sd:
            self.app.netserver_from_endpoint_sd.close()

        self.state = USB.state_detached

    def run(self):
        self.app.service_irqs()

    def ack_status_stage(self):
        self.app.ack_status_stage()

    @mutable('device_descriptor')
    def get_descriptor(self, n):

        bLength = 18
        bDescriptorType = 1
        bMaxPacketSize0 = self.max_packet_size_ep0
        d = struct.pack(
            '<BBHBBBBHHHBBBB',
            bLength,
            bDescriptorType,
            self.usb_spec_version,
            self.device_class,
            self.device_subclass,
            self.protocol_rel_num,
            bMaxPacketSize0,
            self.vendor_id,
            self.product_id,
            self.device_rev,
            self.manufacturer_string_id,
            self.product_string_id,
            self.serial_number_string_id,
            len(self.configurations)
        )
        return d

    # IRQ handlers
    #####################################################
    @mutable('device_qualifier_descriptor')
    def get_device_qualifier_descriptor(self, n):

        bLength = 10
        bDescriptorType = 6
        bNumConfigurations = len(self.configurations)
        bReserved = 0
        bMaxPacketSize0 = self.max_packet_size_ep0

        d = struct.pack(
            '<BBHBBBBBB',
            bLength,
            bDescriptorType,
            self.usb_spec_version,
            self.device_class,
            self.device_subclass,
            self.protocol_rel_num,
            bMaxPacketSize0,
            bNumConfigurations,
            bReserved
        )

        return d

    def handle_request(self, req):
        self.logger.debug("received request", req)

        # figure out the intended recipient
        recipient_type = req.get_recipient()
        recipient = None
        index = req.get_index()
        if recipient_type == USB.request_recipient_device:
            recipient = self
        elif recipient_type == USB.request_recipient_interface:
            if (index & 0xff) < len(self.configuration.interfaces):
                recipient = self.configuration.interfaces[(index & 0xff)]
        elif recipient_type == USB.request_recipient_endpoint:
            recipient = self.endpoints.get(index, None)
        elif recipient_type == USB.request_recipient_other:
            recipient = self.configuration.interfaces[0]    # HACK for Hub class

        if not recipient:
            self.logger.warning("invalid recipient, stalling")
            self.app.stall_ep0()
            return

        # and then the type
        req_type = req.get_type()
        handler_entity = None
        if req_type == USB.request_type_standard:
            handler_entity = recipient
        elif req_type == USB.request_type_class:
            handler_entity = recipient.device_class
        elif req_type == USB.request_type_vendor:
            handler_entity = recipient.device_vendor

        if not handler_entity:
            self.logger.warning("invalid handler entity, stalling")
            self.app.stall_ep0()
            return

        if handler_entity == 9:  # HACK: for hub class
            handler_entity = recipient

        handler = handler_entity.request_handlers.get(req.request, None)

        if not handler:
            self.logger.error('request not handled', req)
            self.logger.debug('handler entity type: %s' % (type(handler_entity)))
            self.logger.debug('handler entity: %s' % (handler_entity))
            self.logger.debug('handler_entity.request_handlers: %s' % (handler_entity.request_handlers))

            if self.app.mode == 2 or self.app.mode == 3:

                self.app.stop = True
                return

            if self.app.mode == 1:
                print ("**SUPPORTED???**")
                if self.app.fplog:
                    self.app.fplog.write("**SUPPORTED???**\n")
                self.app.stop = True
                return

            else:

                self.logger.warning("invalid handler, stalling")
                self.app.stall_ep0()

        try:
            handler(req)
        except:
            traceback.print_exc()
            raise

    def handle_data_available(self, ep_num, data):
        if self.state == USB.state_configured and ep_num in self.endpoints:
            endpoint = self.endpoints[ep_num]
            if callable(endpoint.handler):
                endpoint.handler(data)

    def handle_buffer_available(self, ep_num):
        if self.state == USB.state_configured and ep_num in self.endpoints:
            endpoint = self.endpoints[ep_num]
            if callable(endpoint.handler):
                try:
                    endpoint.handler()
                except:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(''.join(traceback.format_stack()))
                    raise

    # standard request handlers
    #####################################################

    # USB 2.0 specification, section 9.4.5 (p 282 of pdf)
    def handle_get_status_request(self, req):
        trace = "Dev:GetSta"
        self.app.fingerprint.append(trace)
        self.logger.verbose("received GET_STATUS request")
        # self-powered and remote-wakeup (USB 2.0 Spec section 9.4.5)
#        response = b'\x03\x00'
        response = b'\x01\x00'
        self.app.send_on_endpoint(0, response)

    # USB 2.0 specification, section 9.4.1 (p 280 of pdf)
    def handle_clear_feature_request(self, req):

        trace = "Dev:CleFea:%d:%d" % (req.request_type, req.value)
        self.app.fingerprint.append(trace)

        self.logger.verbose("received CLEAR_FEATURE request with type 0x%02x and value 0x%02x" % (req.request_type, req.value))
        # self.app.send_on_endpoint(0, b'')

    # USB 2.0 specification, section 9.4.9 (p 286 of pdf)
    def handle_set_feature_request(self, req):
        trace = "Dev:SetFea"
        self.app.fingerprint.append(trace)
        self.logger.verbose("received SET_FEATURE request")
        response = b''
        self.app.send_on_endpoint(0, response)

    # USB 2.0 specification, section 9.4.6 (p 284 of pdf)
    def handle_set_address_request(self, req):
        self.address = req.value
        self.state = USB.state_address
        self.ack_status_stage()

        trace = "Dev:SetAdr:%d" % self.address
        self.app.fingerprint.append(trace)

        self.logger.verbose("received SET_ADDRESS request for address", self.address)

    # USB 2.0 specification, section 9.4.3 (p 281 of pdf)
    def handle_get_descriptor_request(self, req):
        dtype = (req.value >> 8) & 0xff
        dindex = req.value & 0xff
        lang = req.index
        n = req.length

        response = None

        trace = "Dev:GetDes:%d:%d" % (dtype, dindex)
        self.app.fingerprint.append(trace)

        self.logger.verbose(("received GET_DESCRIPTOR req %d, index %d, " + "language 0x%04x, length %d") % (dtype, dindex, lang, n))

        response = self.descriptors.get(dtype, None)
        # print ("desc:", self.descriptors)
        if callable(response):
            response = response(dindex)

        if response:
            n = min(n, len(response))
            self.app.verbose += 1
            self.app.send_on_endpoint(0, response[:n])
            self.app.verbose -= 1

            self.logger.notify("sent %d bytes in response" % n)
        else:
            self.app.stall_ep0()

    #
    # No need to mutate this one will mutate
    # USBConfiguration.get_descriptor instead
    #
    def get_configuration_descriptor(self, num):
        if num < len(self.configurations):
            return self.configurations[num].get_descriptor()
        else:
            return self.configurations[0].get_descriptor()

    @mutable('string_descriptor_zero')
    def get_string0_descriptor(self):
        d = struct.pack(
            '<BBBB',
            4,      # length of descriptor in bytes
            3,      # descriptor type 3 == string
            9,      # language code 0, byte 0
            4       # language code 0, byte 1
        )
        return d

    @mutable('string_descriptor')
    def get_string_descriptor(self, num):
        self.logger.debug('get_string_descriptor: %#x (%#x)' % (num, len(self.strings)))
        s = None
        if num <= len(self.strings):
            s = self.strings[num-1].encode('utf-16')
        else:
            s = self.configuration.get_string_by_id(num)
        if not s:
            s = self.strings[0].encode('utf-16')
        # Linux doesn't like the leading 2-byte Byte Order Mark (BOM);
        # FreeBSD is okay without it
        s = s[2:]

        d = struct.pack(
            '<BB',
            len(s) + 2,  # length of descriptor in bytes
            3            # descriptor type 3 == string
        )
        return d + s

    def handle_get_string_descriptor_request(self, num):
        if num == 0:
            return self.get_string0_descriptor()
        else:
            return self.get_string_descriptor(num)

    @mutable('hub_descriptor')
    def handle_get_hub_descriptor_request(self, num):
        bLength = 9
        bDescriptorType = 0x29
        bNbrPorts = 4
        wHubCharacteristics = 0xe000
        bPwrOn2PwrGood = 0x32
        bHubContrCurrent = 0x64
        DeviceRemovable = 0
        PortPwrCtrlMask = 0xff

        hub_descriptor = struct.pack(
            '<BBBHBBBB',
            bLength,              # length of descriptor in bytes
            bDescriptorType,      # descriptor type 0x29 == hub
            bNbrPorts,            # number of physical ports
            wHubCharacteristics,  # hub characteristics
            bPwrOn2PwrGood,       # time from power on til power good
            bHubContrCurrent,     # max current required by hub controller
            DeviceRemovable,
            PortPwrCtrlMask
        )

        return hub_descriptor

    # USB 2.0 specification, section 9.4.8 (p 285 of pdf)
    def handle_set_descriptor_request(self, req):

        trace = "Dev:SetDes"
        self.app.fingerprint.append(trace)

        self.logger.debug("received SET_DESCRIPTOR request")

    # USB 2.0 specification, section 9.4.2 (p 281 of pdf)
    def handle_get_configuration_request(self, req):

        trace = "Dev:GetCon"
        self.app.fingerprint.append(trace)
        if self.verbose > 0:
            self.logger.debug("received GET_CONFIGURATION request")
        self.app.send_on_endpoint(0, b'\x01') #HACK - once configuration supported

    # USB 2.0 specification, section 9.4.7 (p 285 of pdf)
    def handle_set_configuration_request(self, req):

        trace = "Dev:SetCon"
        self.app.fingerprint.append(trace)

        self.logger.debug("received SET_CONFIGURATION request")
        self.supported_device_class_trigger = True

        # configs are one-based
        self.config_num = req.value - 1
        # print ("DEBUG: config_num=", self.config_num)
        self.configuration = self.configurations[self.config_num]
        self.state = USB.state_configured

        # collate endpoint numbers
        self.endpoints = {}
        for i in self.configuration.interfaces:
            for e in i.endpoints:
                self.endpoints[e.number] = e

        # HACK: blindly acknowledge request
        self.ack_status_stage()
        # self.supported()

    # USB 2.0 specification, section 9.4.4 (p 282 of pdf)
    def handle_get_interface_request(self, req):
        trace = "Dev:GetInt"
        self.app.fingerprint.append(trace)
        self.logger.debug("received GET_INTERFACE request")
        if req.index == 0:
            # HACK: currently only support one interface
            self.app.send_on_endpoint(0, b'\x00')
        else:
            self.app.stall_ep0()

    # USB 2.0 specification, section 9.4.10 (p 288 of pdf)
    def handle_set_interface_request(self, req):
        trace = "Dev:SetInt"
        self.app.fingerprint.append(trace)
        self.logger.debug("received SET_INTERFACE request")
        self.app.send_on_endpoint(0, b'')

    # USB 2.0 specification, section 9.4.11 (p 288 of pdf)
    def handle_synch_frame_request(self, req):
        trace = "Dev:SynFra"
        self.app.fingerprint.append(trace)

        self.logger.debug("received SYNCH_FRAME request")


class USBDeviceRequest:
    def __init__(self, raw_bytes):
        """Expects raw 8-byte setup data request packet"""
        (
            self.request_type,
            self.request,
            self.value,
            self.index,
            self.length
        ) = struct.unpack('<BBHHH', raw_bytes[:8])
        self.data = raw_bytes[8:]
        self.raw_bytes = raw_bytes

    def __str__(self):
        s = "dir=%d, type=%d, rec=%d, r=%d, v=%d, i=%d, l=%d" \
                % (self.get_direction(), self.get_type(), self.get_recipient(),
                   self.request, self.value, self.index, self.length)
        return s

    def raw(self):
        """returns request as bytes"""
        b = struct.pack(
            '<BBHHH',
            self.request_type,
            self.request,
            self.value >> 8,
            self.index >> 8,
            self.length >> 8,
        )
        return b

    def get_direction(self):
        return (self.request_type >> 7) & 0x01

    def get_type(self):
        return (self.request_type >> 5) & 0x03

    def get_recipient(self):
        return self.request_type & 0x1f

    # meaning of bits in wIndex changes whether we're talking about an
    # interface or an endpoint (see USB 2.0 spec section 9.3.4)
    def get_index(self):
        rec = self.get_recipient()
        if rec == 1:                # interface
            return self.index
        elif rec == 2:              # endpoint
            return self.index & 0xf

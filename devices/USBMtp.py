# USBMtp.py
#
# Contains class definitions to implement a USB keyboard.
from binascii import unhexlify, hexlify
from struct import pack, unpack
# from USB import *
from USBDevice import USBDevice
from USBConfiguration import USBConfiguration
from USBInterface import USBInterface
from USBEndpoint import USBEndpoint
from USBVendor import USBVendor
from .wrappers import mutable
from USBBase import _MyLogger


class ResponseCodes(object):
    UNDEFINED = 0x2000
    OK = 0x2001
    GENERAL_ERROR = 0x2002
    SESSION_NOT_OPEN = 0x2003
    INVALID_TRANSACTION_ID = 0x2004
    OPERATION_NOT_SUPPORTED = 0x2005
    PARAMETER_NOT_SUPPORTED = 0x2006
    INCOMPLETE_TRANSFER = 0x2007
    INVALID_STORAGE_ID = 0x2008
    INVALID_OBJECT_HANDLE = 0x2009
    DEVICE_PROP_NOT_SUPPORTED = 0x200A
    INVALID_OBJECT_FORMAT_CODE = 0x200B
    STORAGE_FULL = 0x200C
    OBJECT_WRITE_PROTECTED = 0x200D
    STORE_READ_ONLY = 0x200E
    ACCESS_DENIED = 0x200F
    NO_THUMBNAIL_PRESENT = 0x2010
    SELF_TEST_FAILED = 0x2011
    PARTIAL_DELETION = 0x2012
    STORE_NOT_AVAILABLE = 0x2013
    SPECIFICATION_BY_FORMAT_UNSUPPORTED = 0x2014
    NO_VALID_OBJECT_INFO = 0x2015
    INVALID_CODE_FORMAT = 0x2016
    UNKNOWN_VENDOR_CODE = 0x2017
    CAPTURE_ALREADY_TERMINATED = 0x2018
    DEVICE_BUSY = 0x2019
    INVALID_PARENT_OBJECT = 0x201A
    INVALID_DEVICE_PROP_FORMAT = 0x201B
    INVALID_DEVICE_PROP_VALUE = 0x201C
    INVALID_PARAMETER = 0x201D
    SESSION_ALREADY_OPEN = 0x201E
    TRANSACTION_CANCELLED = 0x201F
    SPECIFICATION_OF_DESTINATION_UNSUPPORTED = 0x2020
    INVALID_OBJECT_PROP_CODE = 0xA801
    INVALID_OBJECT_PROP_FORMAT = 0xA802
    INVALID_OBJECT_PROP_VALUE = 0xA803
    INVALID_OBJECT_REFERENCE = 0xA804
    GROUP_NOT_SUPPORTED = 0xA805
    INVALID_DATASET = 0xA806
    SPECIFICATION_BY_GROUP_UNSUPPORTED = 0xA807
    SPECIFICATION_BY_DEPTH_UNSUPPORTED = 0xA808
    OBJECT_TOO_LARGE = 0xA809
    OBJECT_PROP_NOT_SUPPORTED = 0xA80A


class OperationDataCodes(object):
    GetDeviceInfo = 0x1001
    OpenSession = 0x1002
    CloseSession = 0x1003
    GetStorageIDs = 0x1004
    GetStorageInfo = 0x1005
    GetNumObjects = 0x1006
    GetObjectHandles = 0x1007
    GetObjectInfo = 0x1008
    GetObject = 0x1009
    GetThumb = 0x100A
    DeleteObject = 0x100B
    SendObjectInfo = 0x100C
    SendObject = 0x100D
    InitiateCapture = 0x100E
    FormatStore = 0x100F
    ResetDevice = 0x1010
    SelfTest = 0x1011
    SetObjectProtection = 0x1012
    PowerDown = 0x1013
    GetDevicePropDesc = 0x1014
    GetDevicePropValue = 0x1015
    SetDevicePropValue = 0x1016
    ResetDevicePropValue = 0x1017
    TerminateOpenCapture = 0x1018
    MoveObject = 0x1019
    CopyObject = 0x101A
    GetPartialObject = 0x101B
    InitiateOpenCapture = 0x101C
    GetObjectPropsSupported = 0x9801
    GetObjectPropDesc = 0x9802
    GetObjectPropValue = 0x9803
    SetObjectPropValue = 0x9804
    GetObjectReferences = 0x9810
    SetObjectReferences = 0x9811
    Skip = 0x9820


class ContainerTypes(object):
    Undefined = 0
    Command = 1
    Data = 2
    Response = 3
    Event = 4


class StorageType(object):
    FIXED_ROM = 0x0001
    REMOVABLE_ROM = 0x0002
    FIXED_RAM = 0x0003
    REMOVABLE_RAM = 0x0004


class FSType(object):
    FLAT = 0x0001
    HIERARCHICAL = 0x0002
    DCF = 0x0003


class AccessCaps(object):
    READ_WRITE = 0x0000
    READ_ONLY_WITHOUT_DELETE = 0x0001
    READ_ONLY_WITH_DELETE = 0x0002


class MtpContainer(object):

    def __init__(self, data):
        (
            self.length,
            self.type,
            self.code,
            self.tid,
        ) = unpack('<IHHI', data[:12])
        self.data = data[12:]


def MU8(i):
    return pack('<B', i)


def MU16(i):
    return pack('<H', i)


def MU32(i):
    return pack('<I', i)


def mtp_response(container, status):
    tid = 0 if not container else container.tid
    return MU32(0xC) + MU16(ContainerTypes.Response) + MU16(status) + MU32(tid)


def mtp_error(container, status):
    return (None, mtp_response(container, status))


def mtp_data(container, data):
    return MU32(len(data) + 0xC) + MU16(ContainerTypes.Data) + MU16(container.code) + MU32(container.tid) + data


class MtpDevice(object):
    '''
    Simulate an MTP device.
    This class should handle the MTP traffic itself.
    At this point, the response for all handlers is fixed,
    and based on some captured traffic.
    Maybe someday someone would like to implement MTP device emulation
    in python, which would be cool, but not today :)
    '''
    def __init__(self, app, verbose):
        self.app = app
        self.verbose = verbose
        self.session_data = {}
        self.logger = _MyLogger(verbose, 'MtpDevice')
        self.command_handlers = {
            OperationDataCodes.GetDeviceInfo: self.op_GetDeviceInfo,
            OperationDataCodes.OpenSession: self.op_OpenSession,
            OperationDataCodes.CloseSession: self.op_CloseSession,
            OperationDataCodes.GetStorageIDs: self.op_GetStorageIDs,
            OperationDataCodes.GetStorageInfo: self.op_GetStorageInfo,
            # OperationDataCodes.GetNumObjects: self.op_GetNumObjects,
            OperationDataCodes.GetObjectHandles: self.op_GetObjectHandles,
            OperationDataCodes.GetObjectInfo: self.op_GetObjectInfo,
            OperationDataCodes.GetObject: self.op_GetObject,
            # OperationDataCodes.GetThumb: self.op_GetThumb,
            # OperationDataCodes.DeleteObject: self.op_DeleteObject,
            # OperationDataCodes.SendObjectInfo: self.op_SendObjectInfo,
            # OperationDataCodes.SendObject: self.op_SendObject,
            # OperationDataCodes.InitiateCapture: self.op_InitiateCapture,
            # OperationDataCodes.FormatStore: self.op_FormatStore,
            # OperationDataCodes.ResetDevice: self.op_ResetDevice,
            # OperationDataCodes.SelfTest: self.op_SelfTest,
            # OperationDataCodes.SetObjectProtection: self.op_SetObjectProtection,
            # OperationDataCodes.PowerDown: self.op_PowerDown,
            # OperationDataCodes.GetDevicePropDesc: self.op_GetDevicePropDesc,
            # OperationDataCodes.GetDevicePropValue: self.op_GetDevicePropValue,
            # OperationDataCodes.SetDevicePropValue: self.op_SetDevicePropValue,
            # OperationDataCodes.ResetDevicePropValue: self.op_ResetDevicePropValue,
            # OperationDataCodes.TerminateOpenCapture: self.op_TerminateOpenCapture,
            # OperationDataCodes.MoveObject: self.op_MoveObject,
            # OperationDataCodes.CopyObject: self.op_CopyObject,
            # OperationDataCodes.GetPartialObject: self.op_GetPartialObject,
            # OperationDataCodes.InitiateOpenCapture: self.op_InitiateOpenCapture,
            # OperationDataCodes.GetObjectPropsSupported: self.op_GetObjectPropsSupported,
            # OperationDataCodes.GetObjectPropDesc: self.op_GetObjectPropDesc,
            # OperationDataCodes.GetObjectPropValue: self.op_GetObjectPropValue,
            # OperationDataCodes.SetObjectPropValue: self.op_SetObjectPropValue,
            # OperationDataCodes.GetObjectReferences: self.op_GetObjectReferences,
            # OperationDataCodes.SetObjectReferences: self.op_SetObjectReferences,
            # OperationDataCodes.Skip: self.op_Skip,
        }
        self.storages = {
            0x00010001: {
                'info': '03000200000000606ad60200000000b0dba501000000000000401149006e007400650072006e0061006c002000730074006f007200610067006500000000',
            },
            0x00020001: {
                'info': '040002000000000018b50300000000005a7e0100000000000040085300440020006300610072006400000000',
            }
        }
        self.objects = {}
        objects_0x00010001 = {
            0x00000003: {
                'info': '010001000130000000100000000000000000000000000000000000000000000000000000000000000000000000000000000000000a520069006e00670074006f006e0065007300000010320030003100350030003700320039005400320032003100350033003200000010320030003100350030003700320039005400320032003100350033003200000000',
                'data': '00000000',
            },
            0x000006bd: {
                'info': '01000100003000004100000000000000000000000000000000000000000000000000000000000300000000000000000000000000072e0069006e00640065007800000010320030003100350030003800300031005400300033003400370030003600000010320030003100350030003700320039005400320032003100350033003300000000',
                'data': '00000000',
            },
            0x00000006: {
                'info': '010001000130000000100000000000000000000000000000000000000000000000000000000000000000000000000000000000000950006900630074007500720065007300000010320030003100350031003100310037005400300037003000300031003600000010320030003100350031003100310037005400300037003000300031003600000000',
                'data': '00000000',
            },
            0x00000008: {
                'info': '010001000130000000100000000000000000000000000000000000000000000000000000000000000000000000000000000000000944006f0077006e006c006f0061006400000010320030003100350031003200320037005400310038003500360034003500000010320030003100350031003200320037005400310038003500360034003500000000',
                'data': '00000000',
            },
            0x00001d8b: {
                'info': '010001000130000000100000000000000000000000000000000000000000000000000000000006000000000000000000000000000c530063007200650065006e00730068006f0074007300000010320030003100360030003100320030005400300030003500390030003500000010320030003100360030003100320030005400300030003500390030003500000000',
                'data': '00000000',
            },
            0x00001db7: {
                'info': '010001000b380000329a020000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310035002d00310031002d00310037002d00300035002d00330036002d00310034002e0070006e006700000010320030003100350031003100310037005400300035003300360031003500000010320030003100350031003100310037005400300035003300360031003600000000',
                'data': '00000000',
            },
            0x00001dbd: {
                'info': '010001000130000000100000000000000000000000000000000000000000000000000000000006000000000000000000000000000943004d005f0043006c006f0075006400000010320030003100350031003100310037005400300037003100350035003800000010320030003100350031003100310037005400300037003000300031003600000000',
                'data': '00000000',
            },
            0x00002158: {
                'info': '010001000b380000fbab020000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310035002d00310032002d00310038002d00310032002d00350034002d00320037002e0070006e006700000010320030003100350031003200310038005400310032003500340032003800000010320030003100350031003200310038005400310032003500340032003700000000',
                'data': '00000000',
            },
            0x0000241d: {
                'info': '010001000b380000d5ba020000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310036002d00300031002d00310030002d00300030002d00350033002d00310039002e0070006e006700000010320030003100360030003100310030005400300030003500330032003000000010320030003100360030003100310030005400300030003500330032003100000000',
                'data': '00000000',
            },
            0x00002430: {
                'info': '010001000b38000065e0020000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310036002d00300031002d00310032002d00300039002d00330032002d00320034002e0070006e006700000010320030003100360030003100310032005400300039003300320032003400000010320030003100360030003100310032005400300039003300320032003400000000',
                'data': '00000000',
            },
            0x00002431: {
                'info': '010001000b380000b61c030000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310036002d00300031002d00310032002d00310030002d00300035002d00330038002e0070006e006700000010320030003100360030003100310032005400310030003000350033003900000010320030003100360030003100310032005400310030003000350033003800000000',
                'data': '00000000',
            },
            0x00002453: {
                'info': '010001000b380000a885020000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310036002d00300031002d00310034002d00310036002d00300039002d00320030002e0070006e006700000010320030003100360030003100310034005400310036003000390032003100000010320030003100360030003100310034005400310036003000390032003000000000',
                'data': '00000000',
            },
            0x00002495: {
                'info': '010001000b3800003c30090000000000000000000000000000000000000000000000000000008b1d00000000000000000000000023530063007200650065006e00730068006f0074005f0032003000310036002d00300031002d00320030002d00300030002d00350039002d00300034002e0070006e006700000010320030003100360030003100320030005400300030003500390030003500000010320030003100360030003100320030005400300030003500390030003600000000',
                'data': '00000000',
            },
            0x0000054a: {
                'info': '010001000138000098c80100000000000000000000000000000000000000000000000000000008000000000000000000000000003564006500720065006b002d00700072006f0073007000650072006f002d007000630062002d0063006900720063007500690074002d0062006f0061007200640073002d00390036003000380039002d00370032003000780031003200380030002e006a0070006700000010320030003100350030003700330031005400310035003100390033003200000010320030003100350030003700330031005400310035003100390033003200000000',
                'data': '00000000',
            },
            0x0000054b: {
                'info': '01000100013800005d670300013800000000000000000000000000000000000000000000000008000000000000000000000000001849004d0047005f00320030003100350030003700330031005f003100350032003100320035002e006a0070006700000010320030003100350030003700330031005400310035003200310032003500000010320030003100350030003700330031005400310035003200310032003500000000',
                'data': '00000000',
            },
            0x0000218e: {
                'info': '01000100003000003486f5010000000000000000000000000000000000000000000000000000080000000000000000000000000068610074006d0065006c002d0038003200370031002d0038002d006200690074002d006100760072002d006d006900630072006f0063006f006e00740072006f006c006c00650072002d00610074006d006500670061003400380061002d0034003800700061002d003800380061002d0038003800700061002d0031003600380061002d00310036003800700061002d003300320038002d0033003200380070005f006400610074006100730068006500650074005f0063006f006d0070006c006500740065002e00700064006600000010320030003100350031003200320037005400310038003500340032003100000010320030003100350031003200320037005400310038003500340032003000000000',
                'data': '00000000',
            },
            0x00000009: {
                'info': '01000100013000000010000000000000000000000000000000000000000000000000000000000000000000000000000000000000054400430049004d00000010320030003100350030003800310033005400320032003000390031003100000010320030003100350030003800310033005400320032003000390031003100000000',
                'data': '00000000',
            },
            0x00000a40: {
                'info': '0100010001300000002000000000000000000000000000000000000000000000000000000000090000000000000000000000000007430061006d00650072006100000010320030003100360030003200310032005400300039003300350035003300000010320030003100360030003200310032005400300039003300350035003300000000',
                'data': '00000000',
            },
        }
        objects_0x00020001 = {
            0x00000940: {
                'info': '0100020001300000002000000000000000000000000000000000000000000000000000000000090000000000000000000000000007430061006d00650072006100000010320030003100360030003200310032005400300039003300350035003300000010320030003100360030003200310032005400300039003300350035003300000000',
                'data': '00000000',
            },
        }
        obj_handles = b''
        for handle in objects_0x00010001:
            obj_handles += MU32(handle)
        self.storages[0x00010001]['handles'] = hexlify(obj_handles)
        self.objects.update(objects_0x00010001)
        obj_handles = b''
        for handle in objects_0x00020001:
            obj_handles += MU32(handle)
        self.storages[0x00020001]['handles'] = hexlify(obj_handles)
        self.objects.update(objects_0x00020001)

    def handle_data(self, data):
        data, response = self._handle_data(data)
        if data is not None:
            self.app.send_on_endpoint(2, data)
        if response is not None:
            self.app.send_on_endpoint(2, response)

    def _handle_data(self, data):
        '''
        .. todo:: handle events ??
        '''
        self.logger.info('handling data. len: %#x' % len(data))
        if len(data) < 12:
            return mtp_error(None, ResponseCodes.INVALID_CODE_FORMAT)
        container = MtpContainer(data)
        if len(data) != container.length:
            return mtp_error(container, ResponseCodes.INVALID_CODE_FORMAT)
        if container.type == ContainerTypes.Command:
            if container.code in self.command_handlers:
                self.session_data['container_length'] = data[0:4]
                self.session_data['container_type'] = data[4:6]
                self.session_data['container_code'] = data[6:8]
                self.session_data['transaction_id'] = data[8:12]
                self.response_code = ResponseCodes.OK
                handler = self.command_handlers[container.code]
                result = handler(container)
                return (result, mtp_response(container, self.response_code))
        self.logger.error('unhandled code: %#x' % container.code)
        self.logger.error('data: %s' % (hexlify(container.data)))
        return mtp_error(container, ResponseCodes.OPERATION_NOT_SUPPORTED)

    @mutable('mtp_op_GetDeviceInfo_response')
    def op_GetDeviceInfo(self, container):
        # should parse this as well, but it will do for now...
        dev_info = unhexlify(
            '6400060000006400266d006900630072006f0073006f00660074002e006300' +
            '6f006d003a00200031002e0030003b00200061006e00640072006f00690064' +
            '002e0063006f006d003a00200031002e0030003b00000000001e0000000110' +
            '021003100410051006100710081009100a100b100c100d1014101510161017' +
            '101b100198029803980498059810981198c195c295c395c495c59506000000' +
            '0240034004400540064001c80400000001d402d403500150000000001a0000' +
            '000030013004300530083009300b30013802380438073808380b380d3801b9' +
            '02b903b982b983b984b905ba10ba11ba14ba82ba06b908730061006d007300' +
            '75006e006700000009470054002d004900390033003000300000000431002e' +
            '00300000001133003200330030006400300064003100630032003500330037' +
            '003000310031000000'
        )
        return mtp_data(container, dev_info)

    @mutable('mtp_op_OpenSession_response')
    def op_OpenSession(self, container):
        if container.length != 0x10:
            self.response_code = ResponseCodes.INVALID_DATASET
            return None
        self.session_data['session_id'] = container.data
        return None

    @mutable('mtp_op_CloseSession_response')
    def op_CloseSession(self, container):
        return None

    @mutable('mtp_op_GetStorageIDs_response')
    def op_GetStorageIDs(self, container):
        sids = MU32(0x00000002) + MU32(0x00010001) + MU32(0x00020001)
        return mtp_data(container, sids)

    @mutable('mtp_op_GetStorageInfo_response')
    def op_GetStorageInfo(self, container):
        if container.length != 0x10:
            self.response_code = ResponseCodes.INVALID_PARAMETER
            return None
        sid = unpack('<I', container.data)[0]
        if sid not in self.storages:
            self.response_code = ResponseCodes.INVALID_STORAGE_ID
            return None
        storage_info = unhexlify(self.storages[sid]['info'])
        return mtp_data(container, storage_info)

    @mutable('mtp_op_GetNumObjects_response')
    def op_GetNumObjects(self, container):
        return None

    @mutable('mtp_op_GetObjectHandles_response')
    def op_GetObjectHandles(self, container):
        if len(container.data) != 0xc:
            self.response_code = ResponseCodes.INVALID_PARAMETER
            return None
        sid, obj_fmt_code, assoc = unpack('<III', container.data)
        if sid in self.storages:
            resp = unhexlify(self.storages[sid]['handles'])
        elif sid == 0xffffffff:
            resp = b''
            for sid in self.storages:
                resp += unhexlify(self.storages[sid]['handles'])
        else:
            self.response_code = ResponseCodes.INVALID_STORAGE_ID
            return None
        return mtp_data(container, resp)

    @mutable('mtp_op_GetObjectInfo_response')
    def op_GetObjectInfo(self, container):
        if len(container.data) != 4:
            self.response_code = ResponseCodes.INVALID_PARAMETER
            return None
        obj_handle = unpack('<I', container.data)[0]
        if obj_handle in self.objects:
            resp = unhexlify(self.objects[obj_handle]['info'])
            return mtp_data(container, resp)
        else:
            self.response_code = ResponseCodes.INVALID_OBJECT_HANDLE
            return None

    @mutable('mtp_op_GetObject_response')
    def op_GetObject(self, container):
        if len(container.data) != 4:
            self.response_code = ResponseCodes.INVALID_PARAMETER
            return None
        obj_handle = unpack('<I', container.data)[0]
        if obj_handle in self.objects:
            resp = unhexlify(self.objects[obj_handle]['data'])
            return mtp_data(container, resp)
        else:
            self.response_code = ResponseCodes.INVALID_OBJECT_HANDLE
            return None

    @mutable('mtp_op_GetThumb_response')
    def op_GetThumb(self, container):
        return None

    @mutable('mtp_op_DeleteObject_response')
    def op_DeleteObject(self, container):
        return None

    @mutable('mtp_op_SendObjectInfo_response')
    def op_SendObjectInfo(self, container):
        return None

    @mutable('mtp_op_SendObject_response')
    def op_SendObject(self, container):
        return None

    @mutable('mtp_op_InitiateCapture_response')
    def op_InitiateCapture(self, container):
        return None

    @mutable('mtp_op_FormatStore_response')
    def op_FormatStore(self, container):
        return None

    @mutable('mtp_op_ResetDevice_response')
    def op_ResetDevice(self, container):
        return None

    @mutable('mtp_op_SelfTest_response')
    def op_SelfTest(self, container):
        return None

    @mutable('mtp_op_SetObjectProtection_response')
    def op_SetObjectProtection(self, container):
        return None

    @mutable('mtp_op_PowerDown_response')
    def op_PowerDown(self, container):
        return None

    @mutable('mtp_op_GetDevicePropDesc_response')
    def op_GetDevicePropDesc(self, container):
        return None

    @mutable('mtp_op_GetDevicePropValue_response')
    def op_GetDevicePropValue(self, container):
        return None

    @mutable('mtp_op_SetDevicePropValue_response')
    def op_SetDevicePropValue(self, container):
        return None

    @mutable('mtp_op_ResetDevicePropValue_response')
    def op_ResetDevicePropValue(self, container):
        return None

    @mutable('mtp_op_TerminateOpenCapture_response')
    def op_TerminateOpenCapture(self, container):
        return None

    @mutable('mtp_op_MoveObject_response')
    def op_MoveObject(self, container):
        return None

    @mutable('mtp_op_CopyObject_response')
    def op_CopyObject(self, container):
        return None

    @mutable('mtp_op_GetPartialObject_response')
    def op_GetPartialObject(self, container):
        return None

    @mutable('mtp_op_InitiateOpenCapture_response')
    def op_InitiateOpenCapture(self, container):
        return None

    @mutable('mtp_op_GetObjectPropsSupported_response')
    def op_GetObjectPropsSupported(self, container):
        return None

    @mutable('mtp_op_GetObjectPropDesc_response')
    def op_GetObjectPropDesc(self, container):
        return None

    @mutable('mtp_op_GetObjectPropValue_response')
    def op_GetObjectPropValue(self, container):
        return None

    @mutable('mtp_op_SetObjectPropValue_response')
    def op_SetObjectPropValue(self, container):
        return None

    @mutable('mtp_op_GetObjectReferences_response')
    def op_GetObjectReferences(self, container):
        return None

    @mutable('mtp_op_SetObjectReferences_response')
    def op_SetObjectReferences(self, container):
        return None

    @mutable('mtp_op_Skip_response')
    def op_Skip(self, container):
        return None

    def get_mutation(self, stage, data=None):
        '''
        :param stage: stage name
        :param data: dictionary (string: bytearray) of data for the fuzzer (default: None)
        :return: mutation for current stage, None if not current fuzzing stage
        '''
        return self.app.get_mutation(stage, data)

    def get_session_data(self, stage):
        '''
        If an entity wants to pass specific data to the fuzzer when getting a mutation,
        it could return a session data here.
        This session data should be a dictionary of string:bytearray.
        The keys of the dictionary should match the keys in the templates.

        :param stage: stage that the session data is for
        :return: dictionary of session data
        '''
        return self.session_data


class USBMtpInterface(USBInterface):
    name = "USB MTP interface"

    def __init__(self, app, verbose=0):
        descriptors = {}
        self.mtp_device = MtpDevice(app, verbose)

        endpoints = [
            USBEndpoint(
                app=app,
                number=1,
                direction=USBEndpoint.direction_out,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=512,
                interval=0,
                handler=self.handle_ep1_data_available
            ),
            USBEndpoint(
                app=app,
                number=2,
                direction=USBEndpoint.direction_in,
                transfer_type=USBEndpoint.transfer_type_bulk,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=512,
                interval=0,
                handler=None
            ),
            USBEndpoint(
                app=app,
                number=3,
                direction=USBEndpoint.direction_in,
                transfer_type=USBEndpoint.transfer_type_interrupt,
                sync_type=USBEndpoint.sync_type_none,
                usage_type=USBEndpoint.usage_type_data,
                max_packet_size=512,
                interval=32,
                handler=None
            ),
        ]
        # TODO: un-hardcode string index (last arg before "verbose")
        super(USBMtpInterface, self).__init__(
            app=app,
            interface_number=0,
            interface_alternate=0,
            interface_class=0xff,
            interface_subclass=0xff,
            interface_protocol=0,
            interface_string_index=0,
            verbose=verbose,
            endpoints=endpoints,
            descriptors=descriptors
        )

        # self.device_class = USBMtpClass(app, verbose)
        # self.device_class.set_interface(self)
        # OS String descriptor
        self.add_string_with_id(0xee, 'MSFT100'.encode('utf-16') + b'\x00\x00')

    def handle_ep1_data_available(self, data):
        self.mtp_device.handle_data(data)


class USBMsosVendor(USBVendor):

    def setup_local_handlers(self):
        self.local_handlers = {
            0x00: self.handle_msos_vendor_extended_config_descriptor,
            0x82: self.handle_0x82,
        }

    @mutable('msos_vendor_extended_config_descriptor')
    def handle_msos_vendor_extended_config_descriptor(self, req):
        '''
        Taken from OS_Desc_CompatID
        https://msdn.microsoft.com/en-us/windows/hardware/gg463179
        '''
        def pad(data, pad_len=8):
            to_pad = pad_len - len(data)
            return data + (b'\x00' * to_pad)

        self.property_sections = [
            [0x00, 0x01, pad(b'MTP'), pad(b''), pad(b'', 6)]
        ]
        bcdVersion = 0x0100
        wIndex = 0x00
        bCount = len(self.property_sections)
        reserved = pad(b'\x00', 7)
        properties = b''
        for prop in self.property_sections:
            properties += pack('BB', prop[0], prop[1]) + prop[2] + prop[3] + prop[4]
        payload = pack('<HHB', bcdVersion, wIndex, bCount) + reserved + properties
        dwLength = len(payload) + 4
        payload = pack('<I', dwLength) + payload
        return payload

    @mutable('0x82')
    def handle_0x82(self):
        pass


class USBMtpDevice(USBDevice):
    name = "USB MTP device"

    def __init__(self, app, vid, pid, rev, verbose=0, **kwargs):
        interface = USBMtpInterface(app, verbose=verbose)
        config = USBConfiguration(
            app=app,
            configuration_index=1,
            configuration_string="Android MTP Device",
            interfaces=[interface]
        )
        super(USBMtpDevice, self).__init__(
            app=app,
            device_class=0,
            device_subclass=0,
            protocol_rel_num=0,
            max_packet_size_ep0=64,
            vendor_id=vid,
            product_id=pid,
            device_rev=rev,
            manufacturer_string="Samsung Electronics Co., Ltd",
            product_string="GT-I9250 Phone [Galaxy Nexus](Mass storage mode)",
            serial_number_string="00001",
            configurations=[config],
            descriptors={},
            verbose=verbose
        )
        self.device_vendor = USBMsosVendor(app=app, verbose=verbose)
        self.device_vendor.set_device(self)

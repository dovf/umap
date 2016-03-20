#!/usr/bin/env python
'''
Umap & Kitty integration
This script initializes and runs the USB device stack

Usage:
    umap_stack.py (fuzz|nofuzz) -P=SERIAL_PORT -C=DEVICE_CLASS [-d=SECONDS] [-i=HOST] [-p=PORT] [-v ...]
    umap_stack.py list classes
    umap_stack.py list subclasses <CLASS>

Options:
    -P --port SERIAL_PORT       facedancer's serial port
    -C --class DEVICE_CLASS     class of the device
    -d --delay SECONDS          delay closing the devices SECONDS seconds
    -i --fuzzer-ip HOST         hostname or IP of the fuzzer [default: 127.0.0.1]
    -p --fuzzer-port PORT       port of the fuzzer [default: 26007]
    -v --verbose                verbosity level
'''
import docopt
import traceback
import time
from kitty.remote.rpc import RpcClient
from Facedancer import Facedancer
from MAXUSBApp import MAXUSBApp
from serial import Serial, PARITY_NONE

from USBClass import USBClass
from devices.USBKeyboard import USBKeyboardDevice
from devices.USBAudio import USBAudioDevice
from devices.USBCDC import USBCDCDevice
from devices.USBFtdi import USBFtdiDevice
from devices.USBHub import USBHubDevice
from devices.USBImage import USBImageDevice
from devices.USBMassStorage import USBMassStorageDevice
from devices.USBPrinter import USBPrinterDevice
from devices.USBSmartcard import USBSmartcardDevice
from devices.USBMtp import USBMtpDevice


list_cmd = 'umap_stack.py list classes'

class_map = {
    'audio': {
        'fd_class': USBAudioDevice,
        'classes': [USBClass.Audio],
        'params': {
            'vid': 0x041e, 'pid': 0x0402, 'rev': 0x0001,
        }
    },
    'cdc': {
        'fd_class': USBCDCDevice,
        'classes': [USBClass.CDC, USBClass.CDCData],
        'params': {
            'vid': 0x2548, 'pid': 0x1001, 'rev': 0x0010,
        }
    },
    'ftdi': {
        'fd_class': USBFtdiDevice,
        'classes': [USBClass.VendorSpecific],
        'params': {
            'vid': 0x0403, 'pid': 0x6001, 'rev': 0x0100,
        }
    },
    'hub': {
        'fd_class': USBHubDevice,
        'classes': [USBClass.Hub],
        'params': {
            'vid': 0x05e3, 'pid': 0x0608, 'rev': 0x6477,
        }
    },
    'image': {
        'fd_class': USBImageDevice,
        'classes': [USBClass.Image],
        'params': {
            'vid': 0x04da, 'pid': 0x2374, 'rev': 0x1000, 'usbclass': USBClass.Image,
        }
    },
    'keyboard': {
        'fd_class': USBKeyboardDevice,
        'classes': [USBClass.HID],
        'params': {
            'vid': 0x610b, 'pid': 0x4653, 'rev': 0x1234,
        },
    },
    'mass-storage': {
        'fd_class': USBMassStorageDevice,
        'classes': [USBClass.MassStorage],
        'params': {
            'vid': 0x154b, 'pid': 0x6545, 'rev': 0x0002, 'usbclass': USBClass.MassStorage,
            'subclass': 6,  # SCSI transparent command set
            'proto': 0x50,  # bulk-only (BBB) transport
        }
    },
    'mtp': {
        'fd_class': USBMtpDevice,
        'classes': [USBClass.VendorSpecific],
        'params': {
            'vid': 0x04e8, 'pid': 0x685c, 'rev': 0x0002,
        }
    },
    'printer': {
        'fd_class': USBPrinterDevice,
        'classes': [USBClass.Printer],
        'params': {
            'vid': 0x03f0, 'pid': 0x4417, 'rev': 0x0001,
            'usbclass': USBClass.Printer, 'subclass': 1, 'proto': 2,
        }
    },
    'smartcard': {
        'fd_class': USBSmartcardDevice,
        'classes': [USBClass.SmartCard],
        'params': {
            'vid': 0x0bda, 'pid': 0x0165, 'rev': 0x2361,
        },
    },
}

default_params = {
    'vid': 0x1111,
    'pid': 0x2222,
    'rev': 0x3333,
    'subclass': 0,
    'proto': 0,
}


def build_fuzzer(options):
    if options['nofuzz']:
        return None
    fuzzer = RpcClient(host=options['--fuzzer-ip'], port=int(options['--fuzzer-port']))
    fuzzer.start()
    return fuzzer


def build_device(fuzzer, options):
    sp = Serial(options['--port'], 115200, parity=PARITY_NONE, timeout=2)
    verbosity = options['--verbose']
    logfp = None
    mode = 2
    current_testcase = None
    fd = Facedancer(sp, verbose=verbosity)
    app = MAXUSBApp(fd, logfp, mode, current_testcase, verbose=verbosity, fuzzer=fuzzer)
    dev_class = options['--class']
    if dev_class not in class_map:
        raise Exception('Unknown device: %s, run `%s` to list supported devices' % (dev_class, list_cmd))
    device_config = class_map[dev_class]
    params = default_params.copy()
    params.update(device_config['params'])
    params['verbose'] = verbosity
    device = device_config['fd_class'](app, **params)
    return device


def run_device(device, options):
    delay = options['--delay']
    delay = None if delay is None else float(delay)
    try:
        device.connect()
        device.run()
        if delay:
            print('delaying disconnection for %s seconds' % delay)
            time.sleep(delay)
    except:
        print('Got exception while connecting/running device')
        print(traceback.format_exc())
    device.disconnect()


def kmap_fuzz(options):
    fuzzer = build_fuzzer(options)
    umap = build_device(fuzzer, options)
    run_device(umap, options)


def kmap_list(options):
    if options['classes']:
        for cls in class_map:
            print(cls)
            # print('%-20s%s' % (cls, ', '.join('%02x' % v for v in class_map[cls]['values'])))
    elif options['subclasses']:
        cls = options['<CLASS>']
        if cls not in class_map:
            raise Exception('Unkown class specified. run `%s` to see list of available classes' % (list_cmd))
        if 'subclasses' in class_map[cls]:
            for subclass in class_map[cls]['subclasses']:
                print(subclass)


def main():
    options = docopt.docopt(__doc__)
    if options['list']:
        kmap_list(options)
    elif options['fuzz'] or options['nofuzz']:
        kmap_fuzz(options)


if __name__ == '__main__':
    main()

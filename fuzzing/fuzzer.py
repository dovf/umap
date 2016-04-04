#!/usr/bin/env python
'''
Usage:
    ./fuzzer.py --type=<fuzzing_type> [--kitty-options=<kitty-options>]

Options:
    -k --kitty-options <kitty-options>  options for the kitty fuzzer, use --kitty-options=--help to get a full list
    -t --type <fuzzing_type>            type of fuzzing to perform

Possible fuzzing types: enmeration, smartcard, mass-storage

This example stores the mutations in files under ./tmp/
It also demonstrate how to user kitty fuzzer command line options.
'''
import docopt
from kitty.remote.rpc import RpcServer
from kitty.fuzzers import ClientFuzzer
from kitty.targets import ClientTarget
from kitty.interfaces import WebInterface
from kitty.model import GraphModel

import os
import time
from kitty.controllers import ClientController
from katnip.templates.usb import *


class UmapController(ClientController):
    '''
    Trigger a USB reconnection -
    Signal the Umap to disconnect / reconnect using files.
    '''

    def __init__(self):
        super(UmapController, self).__init__('UmapController')
        self.trigger_dir = '/tmp/umap_kitty'
        self.connect_file = 'trigger_reconnect'
        self.disconnect_file = 'trigger_disconnect'

    def del_file(self, filename):
        path = os.path.join(self.trigger_dir, filename)
        if os.path.isfile(path):
            os.remove(path)

    def cleanup_triggers(self):
        if not os.path.isdir(self.trigger_dir):
            if not os.path.exists(self.trigger_dir):
                os.mkdir(self.trigger_dir)
        self.del_file(self.connect_file)
        self.del_file(self.disconnect_file)

    def setup(self):
        super(UmapController, self).setup()
        self.cleanup_triggers()

    def trigger_connect(self):
        self.logger.info('trigger reconnection')
        self.do(self.connect_file)

    def trigger_disconnect(self):
        self.logger.info('trigger disconnection')
        self.do(self.disconnect_file)

    def trigger(self):
        self.trigger_disconnect()
        time.sleep(0.2)
        self.trigger_connect()

    def do(self, filename):
        count = 0
        path = os.path.join(self.trigger_dir, filename)
        open(path, 'a').close()
        while os.path.isfile(path):
            time.sleep(0.01)
            count += 1
            if count % 1000 == 0:
                self.logger.warning('still waiting for umap_stack to remove the file %s' % path)


def get_model(options):
    fuzzing_type = options['--type']
    model = GraphModel()
    if fuzzing_type == 'enumeration':
        model.connect(device_descriptor)
        model.connect(interface_descriptor)
        model.connect(endpoint_descriptor)
        model.connect(string_descriptor)
        model.connect(string_descriptor_zero)
    elif fuzzing_type == 'smartcard':
        model.connect(smartcard_Escape_response)
        model.connect(smartcard_GetParameters_response)
        model.connect(smartcard_GetSlotStatus_response)
        model.connect(smartcard_IccClock_response)
        model.connect(smartcard_IccPowerOff_response)
        model.connect(smartcard_IccPowerOn_response)
        model.connect(smartcard_SetParameters_response)
        model.connect(smartcard_T0APDU_response)
        model.connect(smartcard_XfrBlock_response)
    elif fuzzing_type == 'mass-storage':
        model.connect(scsi_inquiry_response)
        model.connect(scsi_mode_sense_10_response)
        model.connect(scsi_mode_sense_6_response)
        model.connect(scsi_read_10_response)
        model.connect(scsi_read_capacity_10_response)
        model.connect(scsi_read_format_capacities)
        model.connect(scsi_request_sense_response)
    else:
        msg = '''invalid fuzzing type, should be one of ['enumeration']'''
        raise Exception(msg)
    return model


def main():
    options = docopt.docopt(__doc__)
    fuzzer = ClientFuzzer(name='UmapFuzzer', option_line=options['--kitty-options'])
    fuzzer.set_interface(WebInterface())

    target = ClientTarget(name='USBTarget')
    target.set_controller(UmapController())
    target.set_mutation_server_timeout(10)

    model = get_model(options)
    fuzzer.set_model(model)
    fuzzer.set_target(target)

    remote = RpcServer(host='localhost', port=26007, impl=fuzzer)
    remote.start()


if __name__ == '__main__':
    main()

'''
Kitty Controller for the Umap stack
'''
import os
import time

from kitty.controllers import ClientController

class UmapController(ClientController):
    '''
    Trigger a USB reconnection -
    Signal the Umap to disconnect / reconnect using files.
    '''

    def __init__(self, pre_disconnect_delay=0.0, post_disconnect_delay=0.0):
        super(UmapController, self).__init__('UmapController')
        self.trigger_dir = '/tmp/umap_kitty'
        self.connect_file = 'trigger_reconnect'
        self.disconnect_file = 'trigger_disconnect'
        self.pre_disconnect_delay = pre_disconnect_delay
        self.post_disconnect_delay = post_disconnect_delay

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

    def post_test(self):
        super(UmapController, self).post_test()
        if self.pre_disconnect_delay:
            time.sleep(self.pre_disconnect_delay)
        self.trigger_disconnect()
        if self.post_disconnect_delay:
            time.sleep(self.post_disconnect_delay)
        # reconnection will be handled when trigger() is called by the base class after pre_test


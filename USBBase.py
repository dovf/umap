'''
Common functionality for all USB actors (interface, class, etc.)
'''
import time


start_time = time.time()


class _MyLogger(object):

    def __init__(self, level, name):
        self.level = level
        self.name = name

    def log(self, level, prefix, *args, **kwargs):
        if level <= self.level:
            print('[%s][%10.4f][%s] %s' % (prefix, time.time() - start_time, self.name, ''.join(str(a) for a in args)))

    def always(self, *args, **kwargs):
        self.log(0, 'A', *args, **kwargs)

    def error(self, *args, **kwargs):
        self.log(0, 'E', *args, **kwargs)

    def info(self, *args, **kwargs):
        self.log(0, 'I', *args, **kwargs)

    def warning(self, *args, **kwargs):
        self.log(1, 'W', *args, **kwargs)

    def debug(self, *args, **kwargs):
        self.log(1, 'D', *args, **kwargs)

    def verbose(self, *args, **kwargs):
        self.log(2, 'V', *args, **kwargs)

    def notify(self, *args, **kwargs):
        self.log(3, 'N', *args, **kwargs)


class USBBaseActor(object):

    name = 'ACTOR'

    def __init__(self, app, verbose):
        self.app = app
        self.verbose = verbose
        self.session_data = {}
        self.str_dict = {}
        self.logger = _MyLogger(verbose, type(self).__name__)

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

    def supported(self):
        '''
        Mark current USB class as supported by the host.
        This will tell the application to stop emulating current device.
        '''
        if self.app.mode == 1:
            print (' **SUPPORTED**')
            if self.app.fplog:
                self.app.fplog.write(" **SUPPORTED**\n")
            self.app.stop = True

    def add_string_with_id(self, str_id, s):
        '''
        Add a string to the string dictionary

        :param str_id: id of the string
        :param s: the string
        '''
        self.str_dict[str_id] = s

    def get_string_by_id(self, str_id):
        '''
        Get a string by it's id

        :param str_id: string id
        :return: the string, or None if id does not exist
        '''
        self.logger.debug(self.name + ' getting string by id %#x' % str_id)
        if str_id in self.str_dict:
            return self.str_dict[str_id]
        return None

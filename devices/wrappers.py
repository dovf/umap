import traceback
import binascii


def mutable(stage):
    def wrap_f(func):
        def wrapper(self, *args, **kwargs):
            session_data = self.get_session_data(stage)
            data = kwargs.get('fuzzing_data', {})
            data.update(session_data)
            response = self.get_mutation(stage=stage, data=data)
            try:
                if response:
                    print('[+] Got mutation for stage %s' % stage)
                else:
                    print('[*] Calling %-30s "%s"' % (func.__name__, stage))
                    response = func(self, *args, **kwargs)
            except Exception as e:
                print(traceback.format_exc())
                print(''.join(traceback.format_stack()))
                raise e
            if response is not None:
                print('[>] %s' % binascii.hexlify(response))
            return response
        return wrapper
    return wrap_f

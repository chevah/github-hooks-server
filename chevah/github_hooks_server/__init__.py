from twisted.python import log as twisted_log


class OwnLog(object):
    """
    A log to convert all to utf-8.
    """
    def msg(self, message):
        twisted_log.msg(message.encode('utf-8'))


log = OwnLog()

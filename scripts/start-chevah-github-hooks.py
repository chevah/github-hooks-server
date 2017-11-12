#!env python
"""
Entry point for the hooks server.

It setup up event handler and starts twistd.

It reads Trac credentials file and pass all other arguments to twistd web.
twistd arguments are only supported in `--option=X` format.
It also support some non-web twistd commands.

twistd web does not allow passing any extra arguments so we pass them via
the configuration file.
"""
import sys
import logging


from twisted.scripts.twistd import run
from twisted.python import log, failure

from chevah.github_hooks_server.configuration import load_configuration


class TwistedLogHandler(logging.Handler):
    """
    Sends Python stdlib logging output through the Twisted logging system.
    """

    def emit(self, record):
        try:
            info = vars(record)
            msg = self.format(record)
            info['isError'] = (record.levelno >= logging.ERROR)
            if record.exc_info is not None:
                t, v, tb = record.exc_info
                info['failure'] = failure.Failure(v, t, tb)
            info['message'] = record.msg
            log.msg(msg, **info)
        except Exception:
            self.handleError(record)


if __name__ == '__main__':

    if len(sys.argv) < 2:
        raise AssertionError(
            'Launch script with at least path to file holding Trac '
            'credentials.')

    load_configuration(sys.argv[1])

    base_arguments = []
    web_arguments = []
    for argument in sys.argv[2:]:
        if (
            argument.startswith('--pidfile') or
            argument.startswith('--nodaemon')
                ):
            base_arguments.append(argument)
        else:
            web_arguments.append(argument)

    sys.argv = ['twistd']
    sys.argv.extend(base_arguments)
    sys.argv.extend([
        'web',
        '--class', 'chevah.github_hooks_server.server.resource',
        ])
    sys.argv.extend(web_arguments)

    # Set up forwarding of stdlib logs to Twisted.
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = TwistedLogHandler()
    logger.addHandler(handler)

    # Start twistd.
    sys.exit(run())

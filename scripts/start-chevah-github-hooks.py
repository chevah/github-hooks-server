"""
Entry point for the hooks server.

It setup up event handler and starts twistd.

It reads Trac credentials file and pass all other arguments to twistd web.
twistd arguments are only supported in `--option=X` format.
It also support some non-web twistd commands.
"""
import sys

from twisted.python import log
from twisted.scripts.twistd import run

from txghserf.server import CONFIGURATION
from chevah.github_hooks_server.handler import Handler


if __name__ == '__main__':

    if len(sys.argv) < 2:
        raise AssertionError(
            'Launch script with at least path to file holding Trac '
            'credentials.')

    # Read Trac credentials and address.
    with open(sys.argv[1], 'r') as file:
        credentials_and_address = file.read().strip()

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
        '--class', 'txghserf.server.resource',
        ])
    sys.argv.extend(web_arguments)

    handler = Handler(
        trac_url='https://%s/login/xmlrpc' % (credentials_and_address, ),
        )

    def handle_event(event):
        log.msg(str(event))
        log.msg('Received new event "%s" for "%s"' % (event.name, event.hook))
        handler.dispatch(event)

    # Register handlers
    CONFIGURATION['callback'] = handle_event

    # Start twistd.
    sys.exit(run())

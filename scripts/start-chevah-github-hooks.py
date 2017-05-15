#!env python
"""
Entry point for the hooks server.

It setup up event handler and starts twistd.

It reads Trac credentials file and pass all other arguments to twistd web.
twistd arguments are only supported in `--option=X` format.
It also support some non-web twistd commands.

twistd web does not allow passing any extra arguments so we pass them via
the CONFIGURATION global.
"""
import sys

from twisted.scripts.twistd import run

from chevah.github_hooks_server.server import CONFIGURATION


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
        '--class', 'chevah.github_hooks_server.server.resource',
        ])
    sys.argv.extend(web_arguments)

    # Pass the trac credentials in a safer way.
    CONFIGURATION['trac-url'] = credentials_and_address

    # Start twistd.
    sys.exit(run())

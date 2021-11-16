import configparser


def load_configuration(path):
    parser = configparser.ConfigParser()
    parser.read(path)
    if 'github_hooks_server' not in parser.sections():
        raise RuntimeError('Config section not found.')

    config = parser['github_hooks_server']

    CONFIGURATION.update(config)

    # Fix handling of None value.
    if not CONFIGURATION['github-hook-secret']:
        CONFIGURATION['github-hook-secret'] = None


# This should be private.
CONFIGURATION = {
    # Cached list of allowed IP address.
    # Expanded at startup based on CIDR.
    # call `expand_allowed_ips()` if `allow_cidr` is changed at runtime.
    '_allowed_ips': {},

    # Details for the GitHub server from which hooks are received.
    'github-server': 'github.com',
    'github-hook-secret': None,

    # GitHub API key used by react on GitHub.
    'github-token': 'set-a-token'
    }

load_configuration('config.ini')

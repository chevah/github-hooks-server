import configparser


def load_configuration(paths):
    parser = configparser.ConfigParser()
    parser.read(paths)
    if 'github_hooks_server' not in parser.sections():
        import os
        raise RuntimeError(f'Config section not found in files [{paths}] '
                           f'from {os.getcwd()}.')

    config = parser['github_hooks_server']

    CONFIGURATION.update(config)

    # Fix handling of None value.
    if not CONFIGURATION['github-hook-secret']:
        CONFIGURATION['github-hook-secret'] = None

    if CONFIGURATION['default-reviewers']:
        pairs = [
            pair.split(':')
            for pair in CONFIGURATION['default-reviewers'].split()
            ]
        CONFIGURATION['default-reviewers'] = {
            k: v.split(',') for k, v in pairs
            }

    return CONFIGURATION


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
    'github-token': 'set-a-token',

    'default-reviewers': {},
    }

load_configuration(['config.ini', 'config-secrets.ini'])

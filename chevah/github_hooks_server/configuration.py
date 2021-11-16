from chevah.github_hooks_server.cidr import get_IP_list
import toml


def load_configuration(path):
    parsed = toml.load(path)
    if not parsed['chevah'] and not parsed['chevah']['github_hooks_server']:
        raise RuntimeError('Config section not found.')

    config = parsed['chevah']['github_hooks_server']

    # Do initial expansion.
    allowed_ips = config.pop('allowed-cidr')
    _expand_allowed_ips(CONFIGURATION, allowed_ips)

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


def _expand_allowed_ips(configuration, new_value):
    """
    Expand the cached list of allowed ips.
    """
    configuration['_allowed_ips'] = {}

    for block in new_value:
        for ip in get_IP_list(block):
            configuration['_allowed_ips'][ip] = True

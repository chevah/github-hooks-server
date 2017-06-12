CONFIGURATION = {
    # Update it from https://api.github.com/meta
    'allow_cidr': [
        '127.0.0.1/24',
        "207.97.227.253/32",
        "50.57.128.197/32",
        "108.171.174.178/32",
        "50.57.231.61/32",
        "204.232.175.64/27",
        "192.30.252.0/22",
        ],
    'callback': None,

    # Cached list of allowed IP address.
    # Expanded at startup based on CIDR.
    # call `expand_allowed_ips()` if `allow_cidr` is changed at runtime.
    '_allowed_ips': {},

    # URL to Trac XML-RPC API.
    'trac-url': 'mock',

    # Details for the GitHub server from which hooks are received.
    'github-server': 'github.com',
    'github-hook-secret': None,

    # Address and credentails for the Buildmaster perspective broker.
    'buildbot-master': 'localhost:1080',
    'buildbot-credentials': 'user:password',

    }

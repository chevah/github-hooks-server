"""
This is the entry point of the server.
"""
from __future__ import absolute_import, unicode_literals
import os
import sys

from klein import resource, route
from twisted.web.static import File
# Import txghserf to install the default routes.
from txghserf import server as txghserf_server
# Shut up the linter.
resource

from chevah.github_hooks_server import highscores
from chevah.github_hooks_server.handler import Handler


STATIC_PATH = os.path.join(os.path.dirname(__file__), 'static')

credentials_and_address = txghserf_server.CONFIGURATION.get('trac-url', 'mock')
highscores.CONFIGURATION['trac-db'] = (txghserf_server.CONFIGURATION['trac-db'],)


# Install our hook handler.
handler = Handler(
    trac_url='https://%s/login/xmlrpc' % (credentials_and_address, ),
    )

def handle_event(event):
    log.msg(str(event))
    log.msg('Received new event "%s" for "%s"' % (event.name, event.hook))
    handler.dispatch(event)

# Register handlers
txghserf_server.CONFIGURATION['callback'] = handle_event


@route('/hooks-static', branch=True)
def static(request):
    """
    All files from static.
    """
    return File(STATIC_PATH)


@route('/highscores',  methods=['GET'])
def hook(request):
    request.setHeader('content-type', 'text/html; charset=utf-8')
    if 'time' in request.args:
        t = highscores.parsetime(request.args['time'][0])
    else:
        t = highscores.Time()
    start, end = highscores.monthRangeAround(t)
    highscores.main(start, end, request.write)
    return ''

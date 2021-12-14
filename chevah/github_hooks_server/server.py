"""
This is the part where requests are dispatched.
"""

try:
    import json
    # Shut up the linter.
    json
except ImportError:
    import simplejson as json

from chevah.github_hooks_server import log
from chevah.github_hooks_server.handler import Handler
from chevah.github_hooks_server.configuration import CONFIGURATION

import azure.functions as func


class Event(object):
    """
    Simple container for GitHub Event.
    """
    def __init__(self, hook, name, content):
        self.hook = hook
        self.name = name
        self.content = content

    def __str__(self):
        return """
        hook: %(hook)s
        event: %(event)s
        content:\n%(content)s
            """ % {
                    'hook': self.hook,
                    'event': self.name,
                    'content': self.content,
                    }


class ServerException(Exception):
    """
    Generic server exception.
    """
    def __init__(self, message):
        self.message = message


def ping(req: func.HttpRequest):
    """
    Simple resource to check that server is up.
    """
    name = req.params.get('name')
    if not name:
        return func.HttpResponse('Pong!')
    return func.HttpResponse(f'Greetings, {name}!')


def pull_request_review(req: func.HttpRequest):
    """
    Called when a PR review overview message is left.
    """
    hook(req, hook_name='pull_request_review')


def issue_comment(req: func.HttpRequest):
    """
    Called when a PR review overview message is left.
    """
    hook(req, hook_name='issue_comment')


def hook(req: func.HttpRequest, hook_name):
    """
    Main hook entry point.

    Check that request is valid, parse the content and then pass
    the object for further processing.
    """
    event_name = req.headers['X-Github-Event']
    if not event_name:
        log.msg('No event name for "%(name)s". %(details)s' % {
                'name': hook_name, 'details': dict(req.headers).items()})
        return "Error:004: What event is this?"

    content = None
    try:
        content = parse_request(req)
    except ServerException as error:
        log.msg('Failed to get json for hook "%(name)s". %(details)s' % {
                'name': hook_name, 'details': error.message})
        return "Error:002: Failed to get hook content."
    except:
        import traceback
        log.msg(
            'Failed to process "%(hook_name)s" "%(event_name)s":\n'
            '%(content)s\n'
            '%(details)s' % {
                'hook_name': hook_name,
                'event_name': event_name,
                'content': content,
                'details': traceback.format_exc(),
                })
        return "Error:003: Internal error"

    event = Event(
        hook=hook_name,
        name=event_name,
        content=content,
        )

    handle_event(event)


def parse_request(req: func.HttpRequest):
    """
    Return the event name nad JSON from req.
    """

    SUPPORTED_CONTENT_TYPES = [
        'application/x-www-form-urlencoded',
        'application/json',
        ]

    content_type = req.headers['Content-Type']
    if not content_type or content_type not in SUPPORTED_CONTENT_TYPES:
        raise ServerException('Unsupported content type.')

    if content_type == 'application/json':
        json_serialization = req.get_body()
    elif content_type == 'application/x-www-form-urlencoded':
        json_serialization = req.params['payload'][0]
    else:
        raise AssertionError('How did we get here?')

    json_dict = json.loads(json_serialization)
    return json_dict


# Set up our hook handler.
credentials_and_address = CONFIGURATION.get('trac-url', 'mock')
handler = Handler(
    trac_url='https://%s/login/xmlrpc' % (credentials_and_address, ),
    github_token=CONFIGURATION['github-token'],
    )


def handle_event(event):
    """
    Called when we got an event.
    """
    log.msg(str(event))
    log.msg('Received new event "%s" for "%s"' % (event.name, event.hook))
    handler.dispatch(event)

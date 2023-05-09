"""
This is the part where requests are dispatched.
"""

import json
import logging
import sys
from urllib.parse import parse_qs

import azure.functions as func
import github3

from chevah.github_hooks_server.configuration import CONFIGURATION
from chevah.github_hooks_server.handler import Handler, HandlerException


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )


sys.excepthook = handle_exception


class Event(object):
    """
    Simple container for GitHub Event.
    """
    def __init__(self, name, content):
        self.name = name
        self.content = content

    def __str__(self):
        return f"""
        event: {self.name}
        content:\n{self.content}
            """


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
    logging.info('Serving a GET ping.')
    name = req.params.get('name')
    if not name:
        return func.HttpResponse('Pong!')
    return func.HttpResponse(f'Greetings, {name}!')


def hook(req: func.HttpRequest):
    """
    Main hook entry point.

    Check that request is valid, parse the content and then pass
    the object for further processing.
    """
    event_name = req.headers['X-Github-Event']
    if not event_name:
        logging.error('No event_name for hook. %(details)s' % {
                'details': dict(req.headers).items()})
        return "Error:004: What event is this?"

    content = None
    try:
        content = parse_request(req)
        event = Event(name=event_name, content=content)
        response = handle_event(event)
        if response:
            return response
        return ''
    except HandlerException as error:
        logging.error(
            f'Failed to handle "{event_name}". {error.message}'
            )
        return "Error:005: Failed to handle event."
    except ServerException as error:
        logging.error(
            f'Failed to get json for hook "{event_name}". {error.message}'
            )
        return "Error:002: Failed to get hook content."
    except:
        import traceback
        logging.error(
            f'Failed to process "{event_name}":\n'
            f'{content}\n'
            f'{traceback.format_exc()}'
            )
        return func.HttpResponse(
            body="Error:003: Internal error", status_code=500
            )


def parse_request(req: func.HttpRequest):
    """
    Return the event name and JSON from req.
    """

    SUPPORTED_CONTENT_TYPES = [
        'application/x-www-form-urlencoded',
        'application/json',
        ]

    content_type = req.headers['Content-Type']
    if not content_type or content_type not in SUPPORTED_CONTENT_TYPES:
        raise ServerException('Unsupported content type.')

    if content_type == 'application/json':
        data_dict = json.loads(req.get_body())
    elif content_type == 'application/x-www-form-urlencoded':
        data_dict = parse_qs(req.get_body())
    else:
        raise AssertionError('How did we get here?')

    return data_dict


handler = None


def handle_event(event):
    """
    Called when we got an event.
    """
    # Set up our hook handler.
    if handler is None:
        handler = Handler(
            github=github3.login(token=CONFIGURATION['github-token']),
            config=CONFIGURATION)

    logging.info(str(event))
    logging.info(f'Received new event "{event.name}".')
    return handler.dispatch(event)

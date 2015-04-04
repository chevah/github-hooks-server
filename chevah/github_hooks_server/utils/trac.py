"""
Handler for Trac interaction.
"""
import xmlrpclib

from twisted.python import log


class TracException(Exception):
    """
    An exception raised by Trac.
    """
    def __init__(self, message='No message.'):
        self.message = message


class TicketNotFoundException(TracException):
    """
    Raised when ticket can not be found.
    """


class Ticket(object):
    """
    """

    def __init__(self, proxy, ticket_id):
        self._proxy = proxy
        self._ticket_id = int(ticket_id)
        self.refresh()

    @property
    def id(self):
        return self._ticket_id

    @property
    def created(self):
        return self._data[1]

    @property
    def updated(self):
        return self._data[2]

    @property
    def attributes(self):
        return self._data[3]

    @property
    def actions(self):
        return self._actions[:]

    def refresh(self):
        """
        Update ticket state.
        """
        multicall = xmlrpclib.MultiCall(self._proxy)
        multicall.ticket.get(self._ticket_id)
        multicall.ticket.getActions(self._ticket_id)
        result = multicall().results
        ticket_data = result[0]
        ticket_actions = result[1]

        # Errors are returned as dictionaries:
        if isinstance(ticket_data, dict):
            if ticket_data['title'] == 'Invalid ticket number':
                raise TicketNotFoundException()
            else:
                raise TracException(str(ticket_data))

        # We only requstes a single ticket.
        self._data = ticket_data[0]
        self._actions = ticket_actions[0]

    def hasAction(self, target):
        """
        Check list of a possible actions on ticket to see if it contains
        action `target`.
        """
        for action in self.actions:
            if action[0] == target:
                return True
        return False

    def reopen(self, comment='', notify=True):
        """
        Reopen a ticket.
        """
        if not self.hasAction(target='reopen'):
            raise TracException(
                'Ticket can not be reopened. %s' % (self.attributes))

        new_attributes = {
            'action': 'reopen',
            '_ts': self.attributes['_ts'],
        }
        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg('[trac][%d] reopened.' % (self.id))

    def close(self, comment='', resolution='fixed', notify=True):
        """
        Close Trac ticket with ID using an optional comment and resolution.
        """
        if not self.hasAction(target='resolve'):
            raise TracException(
                'Ticket can not be closed. %s' % (self.attributes))

        new_attributes = {
            'action': 'resolve',
            'action_resolve_resolve_resolution': resolution,
            '_ts': self.attributes['_ts'],
        }

        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg('[trac][%d] closed.' % (self.id))

    def requestReview(
            self, new_owner=None, comment='', cc='', pull_url='', notify=True):
        """
        Set ticket in needs_review state.
        """
        if not self.hasAction(target='request_review'):
            raise TracException(
                'Ticket can not be reviews. %s' % (self.attributes))

        if not new_owner:
            new_owner = self.attributes['owner']

        new_attributes = {
            'action': 'request_review',
            'action_request_review_reassign_owner': new_owner,
            'cc': cc,
            'branch': pull_url,
            '_ts': self.attributes['_ts'],
        }

        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg(u'[trac][%d] needs review.' % (self.id))

    def requestChanges(self, comment='', notify=True):
        """
        Set request changes state.
        """
        if not self.hasAction(target='request_changes'):
            raise TracException(
                'Ticket can not request changes. %s' % (self.attributes))

        new_attributes = {
            'action': 'request_changes',
            'priority': 'High',
            '_ts': self.attributes['_ts'],
        }

        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg('[trac][%d] needs changes.' % (self.id))

    def requestMerge(self, comment='', cc='', notify=True):
        """
        Set request merge state.
        """
        if not self.hasAction(target='request_merge'):
            raise TracException(
                'Ticket can not request merge. %s' % (self.attributes))
        new_attributes = {
            'action': 'request_merge',
            'cc': cc,
            '_ts': self.attributes['_ts'],
        }

        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg('[trac][%d] needs changes.' % (self.id))

    def update(self, attributes, comment='', notify=True):
        """
        Update ticket attributes, leaving the same state.
        """
        new_attributes = {
            'action': 'leave',
            '_ts': self.attributes['_ts'],
        }

        for key, value in attributes.items():
            new_attributes[key] = value

        self._proxy.ticket.update(
            self.id,
            comment,
            new_attributes,
            notify,
            )
        log.msg('[trac][%d] updated with %s.' % (self.id, attributes))


class Trac(object):
    """
    Trac is initialized with an URL to XML-RPC login.

    trac = Trac(
        login_url="https://user:pass@host:port/login/xmlrpc",
        )
    """

    def __init__(self, login_url):
        self.login_url = login_url
        self.server = xmlrpclib.ServerProxy(self.login_url)

    def getTicket(self, ticket_id):
        """
        Return a Trac ticket or None if it can not be found.
        """
        try:
            return Ticket(proxy=self.server, ticket_id=ticket_id)
        except TicketNotFoundException:
            return None

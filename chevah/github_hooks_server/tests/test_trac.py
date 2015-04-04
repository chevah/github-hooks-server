"""
Tests for Trac integrations.
"""

from unittest import TestCase

from chevah.github_hooks_server.utils.trac import Trac


# Tests are done against the staging server.
_login_url = (
    "https://pqm-staging:pqmisthebest@trac-staging.chevah.com/login/xmlrpc"
    )


class TestTrac(TestCase):
    """
    Test for Trac.
    """
    trac = Trac(login_url=_login_url)

    def test_getTicket_not_found(self):
        """
        None is returned if ticket could not be found.
        """
        # Make sure the ticket does not exists
        ticket = self.trac.getTicket(11111)

        self.assertIsNone(ticket)

    def test_getTicket_ok(self):
        """
        Trac can return a ticket object and ticket id can also be passed
        as a string.
        """
        # We use ticket #1 as it should be alwasy closed.
        ticket = self.trac.getTicket('1')

        self.assertIsNotNone(ticket)
        self.assertEqual(1, ticket.id)
        self.assertIsNotNone(ticket.created)
        self.assertIsNotNone(ticket.updated)
        self.assertIsNotNone(ticket.attributes)


class TestTicket(TestCase):
    """
    Test for Trac Ticket.
    """

    trac = Trac(login_url=_login_url)

    def setUp(self):
        super(TestTicket, self).setUp()
        self.ticket = self.trac.getTicket(1)

    def tearDown(self):
        if self.ticket:
            self.ticket.close(notify=False)

    def test_hasAction(self):
        """
        Check ticket.hasAction().
        """
        self.assertTrue(self.ticket.hasAction('reopen'))
        self.assertFalse(self.ticket.hasAction('needs_review'))
        # Ticket was not opened in this test.
        self.ticket = None

    def test_reopen_close(self):
        """
        Stupid functional test to reopen and close a ticket.

        After a ticket is reopned it has state `new`.
        """
        try:
            self.ticket.reopen(notify=False)

            self.ticket.refresh()
            self.assertEqual('new', self.ticket.attributes['status'])
        finally:
            # Close the ticket.
            self.ticket.refresh()
            self.ticket.close(notify=False)
            self.ticket.refresh()
            self.assertEqual('closed', self.ticket.attributes['status'])
            # We do manual ticket close.
            self.ticket = None

    def test_update(self):
        """
        A ticket can be updated leaving the ticket in the same state.
        """
        initial_state = self.ticket.attributes['status']

        try:
            self.ticket.update(
                attributes={'keywords': 'new_value'}, notify=False)

            self.ticket.refresh()
            self.assertEqual(initial_state, self.ticket.attributes['status'])
            self.assertEqual('new_value', self.ticket.attributes['keywords'])
        finally:
            self.ticket.refresh()
            self.ticket.update(
                attributes={'keywords': ''}, notify=False)
            # Ticket does not need to be closed.
            self.ticket = None

    def test_requestReview_requestChanges(self):
        """
        Stupid functional test to request review and needs_changs for a
        ticket.
        """
        cc = 'io, tu'
        pull_url = 'http://www.chevah.com/pull/url'
        # Ticket must be opened to go to review.
        self.ticket.reopen(notify=False)
        self.ticket.refresh()

        self.ticket.requestReview(
            cc=cc,
            pull_url=pull_url,
            notify=False)

        self.ticket.refresh()
        self.assertEqual('needs_review', self.ticket.attributes['status'])
        self.assertEqual(cc, self.ticket.attributes['cc'])
        self.assertEqual(pull_url, self.ticket.attributes['branch'])

        self.ticket.requestChanges(notify=False)

        self.ticket.refresh()
        self.assertEqual('in_work', self.ticket.attributes['status'])
        self.assertEqual('High', self.ticket.attributes['priority'])

    def test_requestReview_requestMerge(self):
        """
        Stupid functional test to request review and then request merge for a
        ticket.
        """
        cc = 'io, tu'
        pull_url = 'http://www.chevah.com/pull/url'
        # Ticket must be opened to go to review.
        self.ticket.reopen(notify=False)
        self.ticket.refresh()

        self.ticket.requestReview(cc=cc, pull_url=pull_url, notify=False)
        self.ticket.refresh()

        self.ticket.requestMerge(cc=cc, notify=False)
        self.ticket.refresh()

        self.assertEqual('needs_merge', self.ticket.attributes['status'])
        self.assertEqual(cc, self.ticket.attributes['cc'])

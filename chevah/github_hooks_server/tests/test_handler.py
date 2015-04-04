from unittest import TestCase

from mock import Mock
from txghserf.server import Event
from twisted.python import log

from chevah.github_hooks_server.handler import Handler


class TestHandler(TestCase):
    """
    Tests for push handler.
    """

    def setUp(self):
        super(TestHandler, self).setUp()
        self.handler = Handler(trac_url='mock')
        self.handler.trac = Mock()
        self.logs = []
        log.addObserver(self.recordEvent)

    def recordEvent(self, event):
        """
        Keep track of all event.
        """
        self.logs.append(event)

    def tearDown(self):
        log.removeObserver(self.recordEvent)
        for entry in self.logs:
            if isinstance(entry['message'][0], unicode):
                raise AssertionError('Log message is unicode')
        super(TestHandler, self).tearDown()

    def test_push_not_master(self):
        """
        Event will not be process by push if it is not for master.
        """
        content = {
            u'ref': u'refs/heads/780-branch',
            }
        event = Event(hook='some', name='push', content=content)

        self.handler.dispatch(event)

        self.assertFalse(self.handler.trac.getTicket.called)

    def test_push_no_ticket(self):
        """
        Event will not be process if commits does not contain a ticket.
        """
        content = {
            u'ref': u'refs/heads/master',
            u'commits': [{u'message': u'Normal message r\xc9sume'}],
            }
        event = Event(hook='some', name='push', content=content)

        self.handler.dispatch(event)

        self.assertFalse(self.handler.trac.getTicket.called)

    def test_push_with_ticket(self):
        """
        Event will not be process if commits does not contain a ticket.
        """
        content = {
            'ref': 'refs/heads/master',
            'commits': [
                {'message': u'Normal message r\xc9sume'},
                {'message': u'[#123] Normal message r\xc9sume'},
                {'message': u'Normal message r\xc9sume'},
                ],
            }
        event = Event(hook='some', name='push', content=content)

        self.handler.dispatch(event)

        self.assertTrue(self.handler.trac.getTicket.called)
        self.handler.trac.getTicket.assert_called_once_with(123)
        self.handler._current_ticket.close.assert_called_once()

    def test_issue_comment_no_pull(self):
        """
        Nothing happens when issue_comment is not on a pull request.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': None},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': u'r\xc9sume',
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'r\xc9sume **needs-review**',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertFalse(self.handler.trac.getTicket.called)

    def test_issue_comment_no_ticket(self):
        """
        Noting happend is pull request title does not contain a ticket.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'Some message r\xc9sume.',
                u'body': u'r\xc9sume',
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': 'r\xc9sume **needs-review**',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertFalse(self.handler.trac.getTicket.called)

    def test_issue_comment_no_marker(self):
        """
        Noting happen if comment does not contain a magic word.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': '',
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple words for simple persons r\xc9sume.',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertFalse(self.handler.trac.getTicket.called)

    def test_issue_comment_needs_review(self):
        """
        A needs review request is sent to ticket if body contains
        **needs-review** marker.
        """
        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nreviewers @adiroiban @tu\r\nbla',
                },
            u'comment': {
                u'user': {u'login': 'somebody'},
                u'body': body,
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertTrue(self.handler.trac.getTicket.called)
        self.handler.trac.getTicket.assert_called_once_with(12)
        rc = self.handler._current_ticket.requestReview
        comment = (
            u'somebody requested the review of this ticket.\n\n' + body)
        rc.assert_called_once_with(
            cc='adi, tu',
            comment=comment,
            pull_url='something',
            )

    def test_issue_comment_request_changes(self):
        """
        A needs changes request is sent to ticket if body contains
        **needs-changes** marker.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': '',
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple r\xc9sume \r\n**needs-changes** magic.',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertTrue(self.handler.trac.getTicket.called)
        self.handler.trac.getTicket.assert_called_once_with(12)
        rc = self.handler._current_ticket.requestChanges
        comment = (
            u'somebody requested changes to this ticket.\n\n' +
            content['comment']['body']
            )
        rc.assert_called_once_with(comment=comment)

    def test_issue_comment_approved_last(self):
        """
        A needs merge request is sent to ticket if body contains
        the `changes-approved` marker and the user is the last reviewer.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': u'r\xc9sume bla\r\nreviewers @tu @adiroiban\r\nbla',
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple words r\xc9sume \r\n**changes-approved** p.',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'somebody'}
        self.handler.trac.getTicket = Mock(return_value=ticket)

        self.handler.dispatch(event)

        self.assertTrue(self.handler.trac.getTicket.called)
        self.handler.trac.getTicket.assert_called_once_with(12)
        rc = self.handler._current_ticket.requestMerge
        rc.assert_called_once_with(
            cc=u'tu, adi',
            comment=(
                u'somebody approved changes.\n'
                u'No more reviewers.\n'
                u'Ready to merge.\n\n' + content['comment']['body']),
            )

    def test_issue_comment_approved_still_reviewers(self):
        """
        When body contains the `changes-approved` marker and there are still
        reviewers, the ticket is kept in the same state and new CC list is
        updated.
        """
        content = {
            'issue': {
                'pull_request': {'html_url': 'something'},
                'title': '[#12] Some message.',
                'body': 'bla\r\nreviewers @tu @adiroiban\r\nbla',
                },
            'comment': {
                'user': {'login': 'tu'},
                'body': 'Simple words \r\n**changes-approved** magic.',
                }
            }
        event = Event(hook='some', name='issue_comment', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'tu, adi'}
        self.handler.trac.getTicket = Mock(return_value=ticket)

        self.handler.dispatch(event)

        self.assertTrue(self.handler.trac.getTicket.called)
        self.handler.trac.getTicket.assert_called_once_with(12)
        rc = self.handler._current_ticket.update
        comment = (
            'tu approved changes.\n\n' + content['comment']['body'])
        rc.assert_called_once_with(
            comment=comment,
            attributes={'cc': 'adi'},
            )

    def test_getTicketFromMessage(self):
        """
        test_getTicketFromMessage will parse the message and return
        the ticket id.
        """
        message = u'[#12] Hello r\xc9sume.'
        ticket_id = self.handler._getTicketFromMessage(message)
        self.assertEqual(12, ticket_id)

        message = u'Simle words 12 r\xc9sume.'
        ticket_id = self.handler._getTicketFromMessage(message)
        self.assertIsNone(ticket_id)

    def test_getReviewers_no(self):
        """
        Empty list is returned if message does not contains reviewers.
        """
        message = u'Simple message r\xc9sume\r\nSimple words.'

        result = self.handler._getReviewers(message)

        self.assertEqual([], result)

    def test_getReviewers_ok(self):
        """
        Reviewers are returned as list using one of the reviewers markers.
        """
        markers = [
            'reviewer',
            'reviewer:',
            'reviewers',
            'reviewers:',
            ]

        user_filter = {
            'ala': 'celalalt',
            'bla': 'tra',
        }
        self.handler.USERS_GITHUB_TO_TRAC = user_filter

        for marker in markers:
            message = u'Simple r\xc9sume\r\n%s @io @ala bla\r\nbla' % (marker)

            result = self.handler._getReviewers(message)

            self.assertEqual([u'io', u'celalalt'], result)

    def test_needsReview_false(self):
        """
        False is returned when content does not contain a needs review marker.
        """
        message = u'Simple r\xc9sume that no review\r\nneeds review bogus'

        result = self.handler._needsReview(message)

        self.assertFalse(result)

    def test_needsReview_true(self):
        """
        True is returned if message contains one of the needs review markers.
        """
        markers = [
            'needs_review',
            'need_review',
            '*needs_review*',
            '**needs_review**',
            'needs-review',
            '*needs-review*',
            '**needs-review**',
            ]

        for marker in markers:
            message = u'Simple r\xc9sume\r\n%s bla\r\nbla' % (marker)

            result = self.handler._needsReview(message)

            self.assertTrue(result)

    def test_needsChanges_false(self):
        """
        False is returned when content does not contain a needs changes
        marker.
        """
        message = u'Simple r\xc9sume that no changes\r\nneeds changes bog'

        result = self.handler._needsChanges(message)

        self.assertFalse(result)

    def test_needsChanges_true(self):
        """
        True is returned if message contains one of the needs changes markers.
        """
        markers = [
            'needs_changes',
            'need_changes',
            '*needs_changes*',
            '**needs_changes**',
            'needs-changes',
            '*needs-changes*',
            '**needs-changes**',
            ]

        for marker in markers:
            message = u'Simple r\xc9sume\r\n%s bla\r\nbla' % (marker)

            result = self.handler._needsChanges(message)

            self.assertTrue(result)

    def test_changesApproved_false(self):
        """
        False is returned when content does not contain an approved marker.
        """
        message = u'Simple r\xc9sume  no approve\r\n no approved at'

        result = self.handler._changesApproved(message)

        self.assertFalse(result)

    def test_changesApproved_true(self):
        """
        True is returned if message contains one of the approved markers.
        """
        markers = [
            'changes-approved',
            '*changes-approved*',
            '**changes-approved**',
            '**changes-approve**',
            '**change-approved**',
            'approved-at SHA',
            ]

        for marker in markers:
            message = u'Simple r\xc9sume\r\n%s bla\r\nbla' % (marker)

            result = self.handler._changesApproved(message)

            self.assertTrue(result)

    def test_getRemainingReviewers_not_found(self):
        """
        The list is not changes if user is not found in the list.
        """
        result = self.handler._getRemainingReviewers('ala, bala', 'popa')

        self.assertEqual(['ala', 'bala'], result)

    def test_getRemainingReviewers_found(self):
        """
        The list without the user is returned if user is found in the list.
        """
        result = self.handler._getRemainingReviewers(
            'ala, bala, trala', 'bala')

        self.assertEqual(['ala', 'trala'], result)

    def test_getRemainingReviewers_empty(self):
        """
        Empty list is returned when cc_list contains only the ser..
        """
        result = self.handler._getRemainingReviewers('bala', 'bala')

        self.assertEqual([], result)

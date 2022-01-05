"""
Tests for the hook handler.

The tests are done against a real PR located at
https://github.com/chevah/github-hooks-server/pull/8

The test from here are very fragile as they depend on read GitHub data.
"""
import logging
from unittest import TestCase

import github3
from mock import Mock

from chevah.github_hooks_server.handler import Handler
from chevah.github_hooks_server.server import Event
from chevah.github_hooks_server.tests.private import github_token


class LogAsserter(logging.Handler):
    """
    A log handler that allows asserting events.
    Each assertion consumes the first event.
    At the end of the test, `self.logs` should be empty.
    """
    def __init__(self):
        """
        Initialize the list of logging events to assert.
        """
        super(LogAsserter, self).__init__()
        self.logs = []

    def emit(self, record):
        """
        Keep track of log events, except for logs from site-packages.
        """
        if '/site-packages/' not in record.pathname:
            self.logs.append(record)

    def assertLog(self, expected):
        """
        Check that oldest entry in the log has the text `expected`.
        """
        actual_entry = self.logs.pop(0)
        actual = actual_entry.getMessage()

        if actual != expected:
            raise AssertionError(
                f'Bad log.\nExpecting:\n>{expected}<\nGot:\n>{actual}<')

        if not isinstance(actual, str):
            raise AssertionError(f'Log message should be string: {actual}')

    def complainIfNotEmpty(self):
        """
        Throw an error if there still are events not asserted.
        """
        if self.logs:
            raise AssertionError('Still log messages: %s' % (self.logs,))


class TestLogAsserter(TestCase):
    """
    Check that LogAsserter captures logs.
    """

    def setUp(self):
        super(TestLogAsserter, self).setUp()

        self.log_asserter = LogAsserter()
        self.logger = logging.getLogger()
        self.logger.addHandler(self.log_asserter)
        self.logger.setLevel(0)  # Forward everything to the LogAsserter

    def tearDown(self):
        self.logger.removeHandler(self.log_asserter)
        self.log_asserter.complainIfNotEmpty()
        super(TestLogAsserter, self).tearDown()

    def test_log_capture(self):
        """
        Log events captured by the list and asserted in order.
        """
        logging.debug('some debug message')
        logging.info('some info message')
        logging.warning('some warning message')
        logging.error('some error message')
        logging.critical('some CRITICAL message')

        self.log_asserter.assertLog('some debug message')
        self.log_asserter.assertLog('some info message')
        self.log_asserter.assertLog('some warning message')
        self.log_asserter.assertLog('some error message')
        self.log_asserter.assertLog('some CRITICAL message')

    def test_complainIfNotEmpty_empty(self):
        """
        complainIfNotEmpty does not throw an error when no logs were recorded.
        """
        self.log_asserter.complainIfNotEmpty()

    def test_complainIfNotEmpty_not_empty(self):
        """
        complainIfNotEmpty throws an error when logs were recorded.
        """
        logging.debug('some debug message')
        with self.assertRaises(AssertionError):
            self.log_asserter.complainIfNotEmpty()
        self.log_asserter.assertLog('some debug message')


class TestHandler(TestCase):
    """
    Tests for push handler.
    """

    def setUp(self):
        super(TestHandler, self).setUp()
        self.handler = Handler(
            trac_url='mock',
            github=github3.login(token=github_token)
            )

        self.log_asserter = LogAsserter()
        self.logger = logging.getLogger()
        self.logger.addHandler(self.log_asserter)
        self.logger.setLevel(0)  # Forward events of all severity levels.

    def tearDown(self):
        self.logger.removeHandler(self.log_asserter)
        self.log_asserter.complainIfNotEmpty()
        super(TestHandler, self).tearDown()

    def assertLog(self, expected):
        """
        Forward the assertLog method to the LogAsserter.
        """
        return self.log_asserter.assertLog(expected)

    def test_issue_comment_no_pull(self):
        """
        Nothing happens when issue_comment is not on a pull request.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': None},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': u'r\xc9sume',
                'number': 123,
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'r\xc9sume **needs-review**',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            '[issue_comment] Not a comment on a pull request'
            )

    def test_issue_comment_no_ticket(self):
        """
        It will ignore the fact that the title has no associated Trac ticket
        and will just process the requested action to the hooked PR.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'Some message r\xc9sume.',
                u'body': u'r\xc9sume',
                'number': 123,
                'user': {'login': 'some-guy'},
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': 'r\xc9sume no action',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        # Inform that Trac sync is not done.
        self.assertLog(
            'Pull request has no ticket id in title: '
            'Some message r\xc9sume.'
            )
        # Inform that event is going to be processed.
        self.assertLog(
            '[issue_comment][None] New comment from somebody with reviewers []'
            '\nr\xc9sume no action'
            )

    def test_issue_comment_no_marker(self):
        """
        Noting happen if comment does not contain a magic word.
        """
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': '',
                'number': 123,
                'user': {'login': 'ignored'},
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple words for simple persons r\xc9sume.',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            '[issue_comment][12] New comment from somebody with reviewers []\n'
            'Simple words for simple persons r\xc9sume.'
            )

    def test_issue_comment_no_create(self):
        """
        Noting happen if comment was not created, but rather edited or removed,
        so that we don't trigger the same action multiple times.
        """
        content = {
            'action': 'deleted',
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message r\xc9sume.',
                u'body': '',
                'number': 123,
                'user': {'login': 'ignored'},
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple words for simple persons r\xc9sume.',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog('[issue_comment] Not a created issue comment.')

    def test_pull_request_review_no_ticket_in_title(self):
        """
        Will process the PR request by updating the PR even if the PR title
        is not associated with a Trac Ticket..
        """
        content = {
            'pull_request': {
                'title': 'Some message.',
                'body': 'bla\r\nreviewers @tu @adiroiban\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'review': {
                'user': {'login': 'tu'},
                'body': 'anything here.',
                'state': 'changes_requested',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'tu, adi'}

        self.handler.dispatch(event)

        self.assertLog(
            'Pull request has no ticket id in title: Some message.')
        self.assertLog(
            '[pull_request_review][None] New review from tu as changes_requested\n'
            'anything here.'
            )

    def test_pull_request_review_no_submit_action(self):
        """
        Nothing happens when the action is not one of submission.
        """
        content = {
            'action': 'dismissed',
            'pull_request': {
                'title': 'Some message.',
                'body': 'bla\r\nreviewers @tu @adiroiban\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'review': {
                'user': {'login': 'tu'},
                'body': 'anything here.',
                'state': 'changes_requested',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        self.handler.dispatch(event)

        self.assertLog('[pull_request_review] Not review submission.')


#
# --------------------- needs-review ------------------------------------------
#
    def prepareToNeedReview(self):
        """
        Prepare the PR so that it will need review.

        Assigned is none of the reviewers and PR has other labels.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-changes', 'needs-merge', 'low'])
        issue.edit(assignees=['chevah-robot'])
        initial_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', initial_lables)
        self.assertIn('needs-merge', initial_lables)
        self.assertIn('low', initial_lables)
        self.assertNotIn('needs-review', initial_lables)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertReviewRequested(self):
        """
        Check that the review was requested for the PR.

        Label is needs-review and reviewers are set as assignees.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_lables)
        self.assertIn('low', last_lables)
        self.assertNotIn('needs-changes', last_lables)
        self.assertNotIn('needs-merge', last_lables)
        self.assertCountEqual(
            ['adiroiban', 'hcs0'], [u.login for u in issue.assignees])

    def test_issue_comment_needs_review(self):
        """
        A needs review request is sent to ticket if body contains
        **needs-review** marker and other review labels are removed.
        """
        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nreviewers @adiroiban @hcs0\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            u'comment': {
                u'user': {u'login': 'somebody'},
                u'body': body,
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            "[issue_comment][12] New comment from somebody with reviewers "
            "['adi', 'hcs']\nOne more r\xc9sume\r\n\r\n"
            "**needs-review**\r\n"
            )
        self.assertLog(
            "_setNeedsReview "
            "repo=chevah/github-hooks-server, "
            "issue_id=8, "
            "reviewers=['adi', 'hcs']"
            )
        self.assertReviewRequested()

#
# --------------------- needs-changes -----------------------------------------
#
    def prepareToRequestChanges(self):
        """
        Set up the PR so that we can request changes.

        PR doesn't have the author as assignee and has the needs-review label.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-merge', 'low'])
        issue.edit(assignees=['chevah-robot'])
        initial_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_lables)
        self.assertIn('needs-merge', initial_lables)
        self.assertIn('low', initial_lables)
        self.assertNotIn('needs-changes', initial_lables)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertChangesRequested(self):
        """
        Check that the request changes was done for PR.

        Label is needs-changes and author is set at assignee.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', last_lables)
        self.assertIn('low', last_lables)
        self.assertNotIn('needs-review', last_lables)
        self.assertNotIn('needs-merge', last_lables)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])

    def test_issue_comment_request_changes(self):
        """
        A needs changes request is sent to ticket if body contains
        **needs-changes** marker and the PR is assigned to the original author.
        """
        self.prepareToRequestChanges()
        content = {
            u'issue': {
                'pull_request': {u'html_url': u'something'},
                'title': u'[#12] Some message r\xc9sume.',
                'body': '',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            u'comment': {
                u'user': {u'login': u'somebody'},
                u'body': u'Simple r\xc9sume \r\n**needs-changes** magic.',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            '[issue_comment][12] New comment from somebody with reviewers []\n'
            'Simple r\xc9sume \r\n**needs-changes** magic.'
            )
        self.assertChangesRequested()

    def test_pull_request_review_needs_changes(self):
        """
        When the review has the 'Request changes' action the ticket is put
        into the needs-changes state.
        """
        self.prepareToRequestChanges()
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nreviewers @tu @adiroiban\r\nbla',
                'user': {'login': 'adiroiban'},
                'number': 8,
                },
            'review': {
                'user': {'login': 'tu'},
                'body': 'anything here.',
                'state': 'changes_requested',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'tu, adi'}

        self.handler.dispatch(event)

        self.assertLog(
            '[pull_request_review][42] '
            'New review from tu as changes_requested\n'
            'anything here.'
            )
        self.assertChangesRequested()

#
# --------------------- changes-approved -> needs-merge -----------------------
#
    def prepareToAproveLast(self):
        """
        Set up the PR so that we can approve the changes as last person.

        Only one review is left as assignee and label is not needs-merge
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-changes', 'low'])
        issue.edit(assignees=['chevah-robot'])
        initial_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_lables)
        self.assertIn('needs-changes', initial_lables)
        self.assertIn('low', initial_lables)
        self.assertNotIn('needs-merge', initial_lables)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertMergeRequested(self):
        """
        Check that merge was requested for the PR.

        Label is needs-merge and author is set at assignee.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-merge', last_lables)
        self.assertIn('low', last_lables)
        self.assertNotIn('needs-review', last_lables)
        self.assertNotIn('needs-changes', last_lables)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])

    def test_issue_comment_approved_last(self):
        """
        A needs-merge request is sent to ticket if body contains
        the `changes-approved` marker and the user is the last reviewer.
        """
        self.prepareToAproveLast()
        content = {
            'issue': {
                'pull_request': {u'html_url': u'something'},
                'title': '[#12] Some message r\xc9sume.',
                'body': (
                    'r\xc9sume bla\r\n'
                    'reviewers @chevah-robot @adiroiban\r\n'
                    'bla'
                    ),
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'comment': {
                'user': {'login': 'chevah-robot'},
                'body': 'Simple words r\xc9sume \r\n**changes-approved** p.',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'chevah-robot'}

        self.handler.dispatch(event)

        self.assertLog(
            "[issue_comment][12] New comment from chevah-robot with reviewers "
            "['chevah-robot', 'adi']\nSimple words r\xc9sume \r\n"
            "**changes-approved** p."
            )
        self.assertMergeRequested()

    def test_pull_request_review_approved_last(self):
        """
        When the review was approved and no other reviewers are expected,
        the ticket is set into the needs-merge state.
        """
        self.prepareToAproveLast()
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nreviewers @chevah-robot @adiroiban\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'review': {
                'user': {'login': 'chevah-robot'},
                'body': 'anything here.',
                'state': 'approved',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            '[pull_request_review][42] '
            'New review from chevah-robot as approved\n'
            'anything here.'
            )
        self.assertMergeRequested()

#
# --------------------- changes-approved -> still left to review --------------
#
    def prepareToAproveAnLeaveForReview(self):
        """
        Set up the PR so that we can approve the changes and other reviewers
        still need to review it.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-changes', 'low'])
        issue.edit(assignees=['chevah-robot', 'adiroiban'])
        initial_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_lables)
        self.assertIn('needs-changes', initial_lables)
        self.assertIn('low', initial_lables)
        self.assertNotIn('needs-merge', initial_lables)
        self.assertCountEqual(
            ['chevah-robot', 'adiroiban'], [u.login for u in issue.assignees])

    def assertMergeStillNeeded(self):
        """
        Check that merge is still needed for the PR.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_lables = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_lables)
        self.assertIn('low', last_lables)
        self.assertIn('needs-changes', last_lables)
        self.assertEqual(
            ['chevah-robot'], [u.login for u in issue.assignees])

    def test_issue_comment_approved_still_reviewers(self):
        """
        When body contains the `changes-approved` marker and there are still
        reviewers, the ticket is kept in the same state and new CC list is
        updated.
        """
        self.prepareToAproveAnLeaveForReview()
        content = {
            'issue': {
                'pull_request': {'html_url': 'something'},
                'title': '[#12] Some message.',
                'body': 'bla\r\nreviewers @chevah-robot @adiroiban\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'comment': {
                'user': {'login': 'adiroiban'},
                'body': 'Simple words \r\n**changes-approved** magic.',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            "[issue_comment][12] New comment from adi "
            "with reviewers ['chevah-robot', 'adi']\n"
            "Simple words \r\n**changes-approved** magic."
            )
        self.assertMergeStillNeeded()

    def test_pull_request_review_approved_still_reviewers(self):
        """
        When the review was approved and there are other reviewers,
        the ticket is left in needs-review and reviewer is removed.
        """
        self.prepareToAproveAnLeaveForReview()
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nreviewers @chevah-robot @adiroiban\r\nbla',
                'number': 8,
                'user': {'login': 'pr-author-ignored'},
                },
            'review': {
                'user': {'login': 'adiroiban'},
                'body': 'anything here.',
                'state': 'approved',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'adi, chevah-robot'}

        self.handler.dispatch(event)

        self.assertLog(
            '[pull_request_review][42] New review from adi as approved\n'
            'anything here.'
            )
        self.assertMergeStillNeeded()

    def test_pull_request_review_comment(self):
        """
        Nothing happens when we get a simple review comment.
        """
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nreviewers @tu @adiroiban\r\nbla',
                'user': {'login': 'adiroiban'},
                'number': 8,
                },
            'review': {
                'user': {'login': 'tu'},
                'body': 'anything here.',
                'state': 'commented',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }
        event = Event(name='pull_request_review', content=content)

        ticket = Mock()
        ticket.attributes = {'cc': 'tu, adi'}

        self.handler.dispatch(event)

        self.assertLog(
            '[pull_request_review][42] New review from tu as commented\n'
            'anything here.'
            )

    def test_getTicketFromTitle(self):
        """
        test_getTicketFromTitle will parse the message and return
        the ticket id.
        """
        message = '[#12] Hello r\xc9sume.'
        ticket_id = self.handler._getTicketFromTitle(message)
        self.assertEqual(12, ticket_id)

        message = 'Simle words 12 r\xc9sume.'
        ticket_id = self.handler._getTicketFromTitle(message)
        self.assertIsNone(ticket_id)

        # Where does this change come from? Is it an encoding error?
        # https://github.com/chevah/github-hooks-server/commit/f1f6fe19df5abe1ba726be444534101b3b65c5d6#diff-815f326e9c461297febb2cd06561952a2ec2213c091a14965ba3afee05f4fad8R87-R88
        self.assertLog(
            'Pull request has no ticket id in title: '
            'Simle words 12 r\xc9sume.')

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

        self.assertLog(
            'Current user "popa" not in the list of reviewers ala, bala')

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

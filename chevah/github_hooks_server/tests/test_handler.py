"""
Tests for the hook handler.

The tests in TestHandler are fast and do not need the GitHub API.

The tests in TestLiveHandler are done against a real PR located at
https://github.com/chevah/github-hooks-server/pull/8
These are very fragile as they depend on read GitHub data.
"""
import logging
from unittest import TestCase

import github3

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

    def assertLogEmpty(self):
        """
        Throw an error if there are events not matched by assertLog().
        """
        if self.logs:
            raise AssertionError('Log is not empty: %s' % (self.logs,))

    @classmethod
    def createWithLogger(cls):
        """
        Return a LogAsserter and a Logger connected to it.
        """
        log_asserter = cls()
        logger = logging.getLogger()
        logger.addHandler(log_asserter)
        logger.setLevel(0)  # Forward messages of every severity level.

        return log_asserter, logger


class TestLogAsserter(TestCase):
    """
    Check that LogAsserter captures logs.
    """

    def setUp(self):
        super(TestLogAsserter, self).setUp()

        self.log_asserter, self.logger = LogAsserter.createWithLogger()

    def tearDown(self):
        self.logger.removeHandler(self.log_asserter)
        self.log_asserter.assertLogEmpty()
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

    def test_assertLogEmpty_empty(self):
        """
        assertLogEmpty does not throw an error when no logs were recorded.
        """
        self.log_asserter.assertLogEmpty()

    def test_assertLogEmpty_not_empty(self):
        """
        assertLogEmpty throws an error when logs were recorded.
        """
        logging.debug('some debug message')
        with self.assertRaises(AssertionError):
            self.log_asserter.assertLogEmpty()
        self.log_asserter.assertLog('some debug message')

        # The log is again asserted to be empty during tearDown().


class TestHandler(TestCase):
    """
    Tests for push handler.

    These tests do not need the GitHub API.
    """

    def setUp(self):
        super(TestHandler, self).setUp()
        self.handler = Handler('not a github3 instance')

        self.log_asserter, self.logger = LogAsserter.createWithLogger()

    def tearDown(self):
        self.logger.removeHandler(self.log_asserter)
        self.log_asserter.assertLogEmpty()
        super(TestHandler, self).tearDown()

    def assertLog(self, expected):
        """
        Forward to the LogAsserter method.
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

        self.assertLog('[issue_comment] Not a comment on a pull request')

    def test_issue_comment_no_marker(self):
        """
        Noting happens if comment does not contain a magic word.
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

        # The log is asserted to be empty during tearDown().

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

        self.handler.dispatch(event)

        # The log is asserted to be empty during tearDown().

    def test_getReviewers_no(self):
        """
        Empty list is returned if message does not contains reviewers.
        """
        message = u'Simple message r\xc9sume\r\nSimple words.'

        result = self.handler._getReviewers(message)

        self.assertEqual([], result)

    def test_getReviewers_ok(self):
        """
        Reviewers are returned as list using any of the reviewers markers.
        """
        markers = [
            'reviewer',
            'reviewer:',
            'reviewers',
            'reviewers:',
            ]

        for marker in markers:
            message = u'Simple r\xc9sume\r\n%s @io @ala bla\r\nbla' % (marker)

            result = self.handler._getReviewers(message)

            self.assertEqual([u'io', u'ala'], result)

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


class TestLiveHandler(TestCase):
    """
    Tests requiring a real GitHub connection.
    """
    def setUp(self):
        super(TestLiveHandler, self).setUp()
        self.handler = Handler(github3.login(token=github_token))

        self.log_asserter, self.logger = LogAsserter.createWithLogger()

    def tearDown(self):
        self.logger.removeHandler(self.log_asserter)
        self.log_asserter.assertLogEmpty()
        super(TestLiveHandler, self).tearDown()

    def assertLog(self, expected):
        """
        Forward to the LogAsserter method.
        """
        return self.log_asserter.assertLog(expected)

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
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('needs-merge', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-review', initial_labels)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertReviewRequested(self):
        """
        Check that the review was requested for the PR.

        Label is needs-review and reviewers are set as assignees.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-changes', last_labels)
        self.assertNotIn('needs-merge', last_labels)
        self.assertCountEqual(
            ['adiroiban', 'danuker'], [u.login for u in issue.assignees])

    def test_issue_comment_needs_review(self):
        """
        A needs review request is sent to a PR if body contains
        **needs-review** marker and other review labels are removed.
        """
        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nreviewers @adiroiban @danuker\r\nbla',
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

        self.prepareToNeedReview()
        event = Event(name='issue_comment', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            "_setNeedsReview "
            "event=issue_comment, "
            "repo=chevah/github-hooks-server, "
            "pull_id=8, "
            "reviewers=['adiroiban', 'danuker']"
            )
        self.assertReviewRequested()

    def test_review_requested_needs_review(self):
        """
        When a review is requested from someone,
        the "needs-review" action is also triggered.

        There are two relevant actions under the `pull_request` event:
        `review_requested` and `ready_for_review`.
        https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#pull_request
        """
        actions = ['review_requested', 'ready_for_review']

        for action in actions:
            content = {
                'action': action,
                'pull_request': {
                    'html_url': 'something',
                    'title': '[#12] Some message.',
                    'body': 'bla\r\nreviewers @adiroiban @danuker\r\nbla',
                    'number': 8,
                    'user': {'login': 'adiroiban'},
                    },
                'repository': {
                    'full_name': 'chevah/github-hooks-server',
                    },
                }

            self.prepareToNeedReview()
            event = Event(name='pull_request', content=content)

            self.handler.dispatch(event)

            self.assertLog(
                "_setNeedsReview "
                "event=pull_request, "
                "repo=chevah/github-hooks-server, "
                "pull_id=8, "
                "reviewers=['adiroiban', 'danuker']"
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
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-merge', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-changes', initial_labels)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertChangesRequested(self):
        """
        Check that the request changes was done for PR.

        Label is needs-changes and author is set at assignee.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-review', last_labels)
        self.assertNotIn('needs-merge', last_labels)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])

    def test_issue_comment_request_changes(self):
        """
        A needs changes request is sent to PR if body contains
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
            '_setNeedsChanges '
            'event=issue_comment, '
            'repo=chevah/github-hooks-server, '
            'pull_id=8, '
            'author_name=adiroiban'
            )
        self.assertChangesRequested()

    def test_pull_request_review_needs_changes(self):
        """
        When the review has the 'Request changes' action the PR is put
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

        self.handler.dispatch(event)

        self.assertLog(
            '_setNeedsChanges '
            'event=pull_request_review, '
            'repo=chevah/github-hooks-server, '
            'pull_id=8, '
            'author_name=adiroiban'
            )
        self.assertChangesRequested()

#
# --------------------- changes-approved -> needs-merge -----------------------
#
    def prepareToApproveLast(self):
        """
        Set up the PR so that we can approve the changes as last person.

        Only one review is left as assignee and label is not needs-merge
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-changes', 'low'])
        issue.edit(assignees=['chevah-robot'])
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-merge', initial_labels)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])

    def assertMergeRequested(self):
        """
        Check that merge was requested for the PR.

        Label is needs-merge and author is set at assignee.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-merge', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-review', last_labels)
        self.assertNotIn('needs-changes', last_labels)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])

    def test_issue_comment_approved_last(self):
        """
        A needs-merge request is sent to PR if body contains
        the `changes-approved` marker and the user is the last reviewer.
        """
        self.prepareToApproveLast()
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

        self.handler.dispatch(event)

        self.assertLog(
            "_setApproveChanges "
            "event=issue_comment, "
            "repo=chevah/github-hooks-server, "
            "pull_id=8, "
            "author_name=adiroiban, "
            "reviewer_name=chevah-robot"
            )
        self.assertMergeRequested()

    def test_pull_request_review_approved_last(self):
        """
        When the review was approved and no other reviewers are expected,
        the PR is set into the needs-merge state.
        """
        self.prepareToApproveLast()
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
            '_setApproveChanges '
            'event=pull_request_review, '
            'repo=chevah/github-hooks-server, '
            'pull_id=8, '
            'author_name=adiroiban, '
            'reviewer_name=chevah-robot'
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
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-merge', initial_labels)
        self.assertCountEqual(
            ['chevah-robot', 'adiroiban'], [u.login for u in issue.assignees])

    def assertMergeStillNeeded(self):
        """
        Check that merge is still needed for the PR.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_labels)
        self.assertIn('low', last_labels)
        self.assertIn('needs-changes', last_labels)
        self.assertEqual(
            ['chevah-robot'], [u.login for u in issue.assignees])

    def test_issue_comment_approved_still_reviewers(self):
        """
        When body contains the `changes-approved` marker and there are still
        reviewers, the PR is kept in the same state and new CC list is
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
            "_setApproveChanges "
            "event=issue_comment, "
            "repo=chevah/github-hooks-server, "
            "pull_id=8, "
            "author_name=adiroiban, "
            "reviewer_name=adiroiban"
            )
        self.assertMergeStillNeeded()

    def test_pull_request_review_approved_still_reviewers(self):
        """
        When the review was approved and there are other reviewers,
        the PR is left in needs-review and reviewer is removed.
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

        self.handler.dispatch(event)

        self.assertLog(
            '_setApproveChanges '
            'event=pull_request_review, '
            'repo=chevah/github-hooks-server, '
            'pull_id=8, '
            'author_name=pr-author-ignored, '
            'reviewer_name=adiroiban'
            )
        self.assertMergeStillNeeded()


#
# Failed to process "issue_comment": {'action': 'created', 'issue': {'url': 'https://api.github.com/repos/twisted/twisted/issues/1734', 'repository_url': 'https://api.github.com/repos/twisted/twisted', 'labels_url': 'https://api.github.com/repos/twisted/twisted/issues/1734/labels{/name}', 'comments_url': 'https://api.github.com/repos/twisted/twisted/issues/1734/comments', 'events_url': 'https://api.github.com/repos/twisted/twisted/issues/1734/events', 'html_url': 'https://github.com/twisted/twisted/pull/1734', 'id': 1248059576, 'node_id': 'PR_kwDOAB5LTs44cZRl', 'number': 1734, 'title': 'fix typo in README', 'user': {'login': 'edison12a', 'id': 20975616, 'node_id': 'MDQ6VXNlcjIwOTc1NjE2', 'avatar_url': 'https://avatars.githubusercontent.com/u/20975616?v=4', 'gravatar_id': '', 'url': 'https://api.github.com/users/edison12a', 'html_url': 'https://github.com/edison12a', 'followers_url': 'https://api.github.com/users/edison12a/followers', 'following_url': 'https://api.github.com/users/edison12a/following{/other_user}', 'gists_url': 'https://api.github.com/users/edison12a/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/edison12a/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/edison12a/subscriptions', 'organizations_url': 'https://api.github.com/users/edison12a/orgs', 'repos_url': 'https://api.github.com/users/edison12a/repos', 'events_url': 'https://api.github.com/users/edison12a/events{/privacy}', 'received_events_url': 'https://api.github.com/users/edison12a/received_events', 'type': 'User', 'site_admin': False}, 'labels': [], 'state': 'open', 'locked': False, 'assignee': None, 'assignees': [], 'milestone': None, 'comments': 1, 'created_at': '2022-05-25T12:58:44Z', 'updated_at': '2022-07-07T15:57:50Z', 'closed_at': None, 'author_association': 'NONE', 'active_lock_reason': None, 'draft': False, 'pull_request': {'url': 'https://api.github.com/repos/twisted/twisted/pulls/1734', 'html_url': 'https://github.com/twisted/twisted/pull/1734', 'diff_url': 'https://github.com/twisted/twisted/pull/1734.diff', 'patch_url': 'https://github.com/twisted/twisted/pull/1734.patch', 'merged_at': None}, 'body': None, 'reactions': {'url': 'https://api.github.com/repos/twisted/twisted/issues/1734/reactions', 'total_count': 0, '+1': 0, '-1': 0, 'laugh': 0, 'hooray': 0, 'confused': 0, 'heart': 0, 'rocket': 0, 'eyes': 0}, 'timeline_url': 'https://api.github.com/repos/twisted/twisted/issues/1734/timeline', 'performed_via_github_app': None, 'state_reason': None}, 'comment': {'url': 'https://api.github.com/repos/twisted/twisted/issues/comments/1177843604', 'html_url': 'https://github.com/twisted/twisted/pull/1734#issuecomment-1177843604', 'issue_url': 'https://api.github.com/repos/twisted/twisted/issues/1734', 'id': 1177843604, 'node_id': 'IC_kwDOAB5LTs5GNHeU', 'user': {'login': 'adiroiban', 'id': 204609, 'node_id': 'MDQ6VXNlcjIwNDYwOQ==', 'avatar_url': 'https://avatars.githubusercontent.com/u/204609?v=4', 'gravatar_id': '', 'url': 'https://api.github.com/users/adiroiban', 'html_url': 'https://github.com/adiroiban', 'followers_url': 'https://api.github.com/users/adiroiban/followers', 'following_url': 'https://api.github.com/users/adiroiban/following{/other_user}', 'gists_url': 'https://api.github.com/users/adiroiban/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/adiroiban/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/adiroiban/subscriptions', 'organizations_url': 'https://api.github.com/users/adiroiban/orgs', 'repos_url': 'https://api.github.com/users/adiroiban/repos', 'events_url': 'https://api.github.com/users/adiroiban/events{/privacy}', 'received_events_url': 'https://api.github.com/users/adiroiban/received_events', 'type': 'User', 'site_admin': False}, 'created_at': '2022-07-07T15:57:50Z', 'updated_at': '2022-07-07T15:57:50Z', 'author_association': 'MEMBER', 'body': 'I am testing the automatic PR  labeler here \r\n\r\nneeds-changes', 'reactions': {'url': 'https://api.github.com/repos/twisted/twisted/issues/comments/1177843604/reactions', 'total_count': 0, '+1': 0, '-1': 0, 'laugh': 0, 'hooray': 0, 'confused': 0, 'heart': 0, 'rocket': 0, 'eyes': 0}, 'performed_via_github_app': None}, 'repository': {'id': 1985358, 'node_id': 'MDEwOlJlcG9zaXRvcnkxOTg1MzU4', 'name': 'twisted', 'full_name': 'twisted/twisted', 'private': False, 'owner': {'login': 'twisted', 'id': 716546, 'node_id': 'MDEyOk9yZ2FuaXphdGlvbjcxNjU0Ng==', 'avatar_url': 'https://avatars.githubusercontent.com/u/716546?v=4', 'gravatar_id': '', 'url': 'https://api.github.com/users/twisted', 'html_url': 'https://github.com/twisted', 'followers_url': 'https://api.github.com/users/twisted/followers', 'following_url': 'https://api.github.com/users/twisted/following{/other_user}', 'gists_url': 'https://api.github.com/users/twisted/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/twisted/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/twisted/subscriptions', 'organizations_url': 'https://api.github.com/users/twisted/orgs', 'repos_url': 'https://api.github.com/users/twisted/repos', 'events_url': 'https://api.github.com/users/twisted/events{/privacy}', 'received_events_url': 'https://api.github.com/users/twisted/received_events', 'type': 'Organization', 'site_admin': False}, 'html_url': 'https://github.com/twisted/twisted', 'description': 'Event-driven networking engine written in Python.', 'fork': False, 'url': 'https://api.github.com/repos/twisted/twisted', 'forks_url': 'https://api.github.com/repos/twisted/twisted/forks', 'keys_url': 'https://api.github.com/repos/twisted/twisted/keys{/key_id}', 'collaborators_url': 'https://api.github.com/repos/twisted/twisted/collaborators{/collaborator}', 'teams_url': 'https://api.github.com/repos/twisted/twisted/teams', 'hooks_url': 'https://api.github.com/repos/twisted/twisted/hooks', 'issue_events_url': 'https://api.github.com/repos/twisted/twisted/issues/events{/number}', 'events_url': 'https://api.github.com/repos/twisted/twisted/events', 'assignees_url': 'https://api.github.com/repos/twisted/twisted/assignees{/user}', 'branches_url': 'https://api.github.com/repos/twisted/twisted/branches{/branch}', 'tags_url': 'https://api.github.com/repos/twisted/twisted/tags', 'blobs_url': 'https://api.github.com/repos/twisted/twisted/git/blobs{/sha}', 'git_tags_url': 'https://api.github.com/repos/twisted/twisted/git/tags{/sha}', 'git_refs_url': 'https://api.github.com/repos/twisted/twisted/git/refs{/sha}', 'trees_url': 'https://api.github.com/repos/twisted/twisted/git/trees{/sha}', 'statuses_url': 'https://api.github.com/repos/twisted/twisted/statuses/{sha}', 'languages_url': 'https://api.github.com/repos/twisted/twisted/languages', 'stargazers_url': 'https://api.github.com/repos/twisted/twisted/stargazers', 'contributors_url': 'https://api.github.com/repos/twisted/twisted/contributors', 'subscribers_url': 'https://api.github.com/repos/twisted/twisted/subscribers', 'subscription_url': 'https://api.github.com/repos/twisted/twisted/subscription', 'commits_url': 'https://api.github.com/repos/twisted/twisted/commits{/sha}', 'git_commits_url': 'https://api.github.com/repos/twisted/twisted/git/commits{/sha}', 'comments_url': 'https://api.github.com/repos/twisted/twisted/comments{/number}', 'issue_comment_url': 'https://api.github.com/repos/twisted/twisted/issues/comments{/number}', 'contents_url': 'https://api.github.com/repos/twisted/twisted/contents/{+path}', 'compare_url': 'https://api.github.com/repos/twisted/twisted/compare/{base}...{head}', 'merges_url': 'https://api.github.com/repos/twisted/twisted/merges', 'archive_url': 'https://api.github.com/repos/twisted/twisted/{archive_format}{/ref}', 'downloads_url': 'https://api.github.com/repos/twisted/twisted/downloads', 'issues_url': 'https://api.github.com/repos/twisted/twisted/issues{/number}', 'pulls_url': 'https://api.github.com/repos/twisted/twisted/pulls{/number}', 'milestones_url': 'https://api.github.com/repos/twisted/twisted/milestones{/number}', 'notifications_url': 'https://api.github.com/repos/twisted/twisted/notifications{?since,all,participating}', 'labels_url': 'https://api.github.com/repos/twisted/twisted/labels{/name}', 'releases_url': 'https://api.github.com/repos/twisted/twisted/releases{/id}', 'deployments_url': 'https://api.github.com/repos/twisted/twisted/deployments', 'created_at': '2011-07-01T20:40:42Z', 'updated_at': '2022-07-07T15:13:34Z', 'pushed_at': '2022-07-05T06:31:45Z', 'git_url': 'git://github.com/twisted/twisted.git', 'ssh_url': 'git@github.com:twisted/twisted.git', 'clone_url': 'https://github.com/twisted/twisted.git', 'svn_url': 'https://github.com/twisted/twisted', 'homepage': 'https://www.twisted.org', 'size': 70297, 'stargazers_count': 4644, 'watchers_count': 4644, 'language': 'Python', 'has_issues': True, 'has_projects': False, 'has_downloads': True, 'has_wiki': False, 'has_pages': False, 'forks_count': 1074, 'mirror_url': None, 'archived': False, 'disabled': False, 'open_issues_count': 2745, 'license': {'key': 'other', 'name': 'Other', 'spdx_id': 'NOASSERTION', 'url': None, 'node_id': 'MDc6TGljZW5zZTA='}, 'allow_forking': True, 'is_template': False, 'web_commit_signoff_required': False, 'topics': ['async', 'async-python', 'dns', 'event-driven', 'http', 'imap', 'irc', 'network', 'python', 'smtp', 'ssl', 'tls', 'twisted', 'xmpp'], 'visibility': 'public', 'forks': 1074, 'open_issues': 2745, 'watchers': 4644, 'default_branch': 'trunk'}, 'organization': {'login': 'twisted', 'id': 716546, 'node_id': 'MDEyOk9yZ2FuaXphdGlvbjcxNjU0Ng==', 'url': 'https://api.github.com/orgs/twisted', 'repos_url': 'https://api.github.com/orgs/twisted/repos', 'events_url': 'https://api.github.com/orgs/twisted/events', 'hooks_url': 'https://api.github.com/orgs/twisted/hooks', 'issues_url': 'https://api.github.com/orgs/twisted/issues', 'members_url': 'https://api.github.com/orgs/twisted/members{/member}', 'public_members_url': 'https://api.github.com/orgs/twisted/public_members{/member}', 'avatar_url': 'https://avatars.githubusercontent.com/u/716546?v=4', 'description': ''}, 'sender': {'login': 'adiroiban', 'id': 204609, 'node_id': 'MDQ6VXNlcjIwNDYwOQ==', 'avatar_url': 'https://avatars.githubusercontent.com/u/204609?v=4', 'gravatar_id': '', 'url': 'https://api.github.com/users/adiroiban', 'html_url': 'https://github.com/adiroiban', 'followers_url': 'https://api.github.com/users/adiroiban/followers', 'following_url': 'https://api.github.com/users/adiroiban/following{/other_user}', 'gists_url': 'https://api.github.com/users/adiroiban/gists{/gist_id}', 'starred_url': 'https://api.github.com/users/adiroiban/starred{/owner}{/repo}', 'subscriptions_url': 'https://api.github.com/users/adiroiban/subscriptions', 'organizations_url': 'https://api.github.com/users/adiroiban/orgs', 'repos_url': 'https://api.github.com/users/adiroiban/repos', 'events_url': 'https://api.github.com/users/adiroiban/events{/privacy}', 'received_events_url': 'https://api.github.com/users/adiroiban/received_events', 'type': 'User', 'site_admin': False}}
# Traceback (most recent call last):
# File "/home/site/wwwroot/chevah/github_hooks_server/server.py", line 81, in hook
#  response = handle_event(event)
# File "/home/site/wwwroot/chevah/github_hooks_server/server.py", line 137, in handle_event
# return handler.dispatch(event)
# File "/home/site/wwwroot/chevah/github_hooks_server/handler.py", line 38, in dispatch
# return handler(event)
# File "/home/site/wwwroot/chevah/github_hooks_server/handler.py", line 219, in issue_comment
# reviewers = self._getReviewers(event.content['issue']['body'])
# File "/home/site/wwwroot/chevah/github_hooks_server/handler.py", line 248, in _getReviewers
# for line in message.splitlines(): AttributeError: 'NoneType' object has no attribute 'splitlines'

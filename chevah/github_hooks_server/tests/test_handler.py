"""
Tests for the hook handler.

The tests in TestHandler are fast and do not need the GitHub API.

The tests in TestLiveHandler are done against a real PR located at
https://github.com/chevah/github-hooks-server/pull/8
These are very fragile as they depend on read GitHub data.
"""
import datetime
import logging
import uuid
from unittest import TestCase

import github3
from dateutil.tz import tzutc

from chevah.github_hooks_server.configuration import load_configuration
from chevah.github_hooks_server.handler import Handler
from chevah.github_hooks_server.server import Event
from chevah.github_hooks_server.tests.private import github_token

config = load_configuration('chevah/github_hooks_server/tests/test_config.ini')


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


class NotAGithub3Instance:
    """
    A trap GitHub instance that fails if used in tests that should be offline.
    """


class TestHandler(TestCase):
    """
    Tests for push handler.

    These tests are not allowed to use the GitHub API.
    """

    def setUp(self):
        super(TestHandler, self).setUp()
        self.handler = Handler(NotAGithub3Instance, config=config)

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

    def test_shouldHandlePull(self):
        """
        Return whether we should handle the given pull request.
        See test_config.ini for the repos skipped during testing.
        """
        self.assertTrue(self.handler._shouldHandlePull('chevah/no-skip', '8'))
        self.assertTrue(self.handler._shouldHandlePull('chevah/no-skip', 8))

        self.assertFalse(self.handler._shouldHandlePull('chevah/to-skip', 7))
        self.assertFalse(self.handler._shouldHandlePull('chevah/to-skip', 8))
        self.assertFalse(self.handler._shouldHandlePull('chevah/to-skip', '7'))
        self.assertFalse(self.handler._shouldHandlePull('chevah/to-skip', '8'))

        self.assertTrue(self.handler._shouldHandlePull('chevah/pr-skip', 7))
        self.assertFalse(self.handler._shouldHandlePull('chevah/pr-skip', 8))
        self.assertTrue(self.handler._shouldHandlePull('chevah/pr-skip', '7'))
        self.assertFalse(self.handler._shouldHandlePull('chevah/pr-skip', '8'))

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
                'requested_reviewers': [],
                'requested_teams': [],
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
        Empty list is returned if message does not contain reviewers,
        and no default-reviewers are configured for the given repository.
        """
        message = u'Simple message r\xc9sume\r\nSimple words.'

        result = self.handler._getReviewers(
            message, 'some/repo', 'ready_for_review')

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

            result = self.handler._getReviewers(message, None, 'ready_for_review')

            self.assertEqual([u'io', u'ala'], result)

    def test_getReviewers_spaces(self):
        """
        Reviewers are parsed into a list
        even if there are multiple blanks between the marker and the nicknames.
        """
        for message in [
            u'Simple r\xc9sume\r\nreviewers:  @io @ala bla\r\nbla',
            u'Simple r\xc9sume\r\nreviewers:\t@io @ala bla\r\nbla',
            u'Simple r\xc9sume\r\nreviewers:\t @io @ala bla\r\nbla',
            u'Simple r\xc9sume\r\nreviewers: \t@io @ala bla\r\nbla',
            u'Simple r\xc9sume\r\nreviewers:\t\t@io @ala bla\r\nbla',
            u'Simple r\xc9sume\r\nreviewers:\t\t@io @ala bla\r\n@bla',
            u'Simple r\xc9sume\r\nreviewers:\t\t@io @ala bla\n@bla',
            ]:

            result = self.handler._getReviewers(
                message, 'some/repo', 'ready_for_review')

            self.assertEqual([u'io', u'ala'], result, f'Message was: {message}')

    def test_getReviewers_None(self):
        """
        The message body can be None.

        Example: https://github.com/twisted/twisted/pull/1734
        """
        result = self.handler._getReviewers(
            message=None, repo='some/repo', action='ready_for_review')

        self.assertEqual([], result)

    def test_getReviewers_default_repo(self):
        """
        Auto-fills reviewers if there are defaults for the repo.
        """
        result = self.handler._getReviewers(
            message=None, repo='test_org/test_repo', action='ready_for_review')

        self.assertEqual(['test_org/test_reviewers'], result)

    def test_getReviewers_default_repo_multiple_reviewers(self):
        """
        Returns all reviewers if there are multiple ones for a repo.
        """
        result = self.handler._getReviewers(
            message=None, repo='test_org/test_repo2', action='ready_for_review'
            )

        self.assertEqual(['reviewer1', 'reviewer2'], result)

    def test_getReviewers_default_orgwide(self):
        """
        When no reviewer is in the message,
        and no default-reviewer is configured for the repo,
        returns the configured reviewer of an organization-wide default rule.
        """
        result = self.handler._getReviewers(
            message=None, repo='test_orgwide/some_repo', action='ready_for_review'
            )
        self.assertEqual(['reviewer3'], result)

    def test_getReviewers_default_repo_when_also_orgwide(self):
        """
        When no reviewer is in the message,
        and a default-reviewer is configured for both the repo and the org,
        returns the repo-wide reviewer, because it is more specific.
        """
        result = self.handler._getReviewers(
            message=None,
            repo='test_orgwide/repo_exception',
            action='ready_for_review'
            )

        self.assertEqual(['reviewer4'], result)

    def test_splitReviewers(self):
        """
        Splits reviewers in individuals and teams, as a dictionary.
        Teams are stripped of the repository prefix and slash.
        """
        self.assertEqual(
            {
                'reviewers': ['account'],
                'team_reviewers': ['team'],
            },
            self.handler._splitReviewers(['account', 'chevah/team'])
            )

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

            # For Twisted.
            'please-review',
            'review-please',
            'please review',
            'review please',
            'PLEASE-REVIEW',
            'REVIEW-PLEASE',
            'Please review',
            'REVIEW PLEASE',
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


class TestHasOnlyApprovingReviews(TestHandler):
    def test_empty(self):
        """
        Returns True for an empty review list.
        """
        pull = StubPull(reviews=[])
        self.assertTrue(self.handler._hasOnlyApprovingReviews(pull))

    def test_approved(self):
        """
        An approved review returns True.
        """
        pull = StubPull(reviews=[StubReview('APPROVED')])
        self.assertTrue(self.handler._hasOnlyApprovingReviews(pull))

    def test_approved_text(self):
        """
        A comment that matches the "changes approved" regex returns True.
        """
        pull = StubPull(
            reviews=[StubReview('COMMENTED', body='changes-approved')])
        self.assertTrue(self.handler._hasOnlyApprovingReviews(pull))

    def test_changes_requested(self):
        """
        Returns False for a denied review.
        """
        pull = StubPull(reviews=[StubReview('CHANGES_REQUESTED')])
        self.assertFalse(self.handler._hasOnlyApprovingReviews(pull))

    def test_one_denied(self):
        """
        Returns False for an approved and a denied review.
        """
        pull = StubPull(reviews=[
            StubReview('APPROVED'), StubReview('CHANGES_REQUESTED')])
        self.assertFalse(self.handler._hasOnlyApprovingReviews(pull))

    def test_two_approved(self):
        """
        Returns True for two approved reviews.
        """
        pull = StubPull(reviews=[
            StubReview('APPROVED'), StubReview('APPROVED')])
        self.assertTrue(self.handler._hasOnlyApprovingReviews(pull))

    def test_latest_approval_from_same_user(self):
        """
        When the latest review from a user approves, it returns True.
        This happens even if an earlier one requires changes.
        Times are reversed in the review list, to test that it sorts.
        """
        time1 = datetime.datetime(2022, 7, 13, 11, 42, 52, tzinfo=tzutc())
        time2 = datetime.datetime(2023, 7, 13, 11, 42, 52, tzinfo=tzutc())
        dan = StubUser('danuker')

        pull = StubPull(reviews=[
            StubReview('APPROVED', submitted_at=time2, user=dan),
            StubReview('CHANGES_REQUESTED', submitted_at=time1, user=dan),
            ])
        self.assertTrue(self.handler._hasOnlyApprovingReviews(pull))

    def test_latest_denial_from_same_user(self):
        """
        When the latest review from a user denies, it returns True.
        This happens even if an earlier one requires changes.
        Times are reversed in the review list, to test that it sorts.
        """
        time1 = datetime.datetime(2022, 7, 13, 11, 42, 52, tzinfo=tzutc())
        time2 = datetime.datetime(2023, 7, 13, 11, 42, 52, tzinfo=tzutc())
        dan = StubUser('danuker')

        pull = StubPull(reviews=[
            StubReview('CHANGES_REQUESTED', submitted_at=time2, user=dan),
            StubReview('APPROVED', submitted_at=time1, user=dan),
            ])
        self.assertFalse(self.handler._hasOnlyApprovingReviews(pull))


class StubPull:
    def __init__(self, reviews):
        self._reviews = reviews

    def reviews(self):
        return self._reviews


class StubReview:
    def __init__(self, state, submitted_at=None, user=None, body=''):
        self.state = state

        if submitted_at is None:
            submitted_at = datetime.datetime(
                2023, 5, 11, 17, 42, 52, tzinfo=tzutc())
        if user is None:
            user = StubUser(uuid.uuid4())

        self.submitted_at = submitted_at
        self.user = user
        self.body = body


class StubUser:
    """
    A stub for a ShortUser returned by Github3.
    """
    def __init__(self, login):
        self.login = login


class StubTeam:
    """
    A stub for a ShortTeam returned by Github3.
    """
    def __init__(self, slug):
        if "/" in slug:
            raise ValueError("Team slug must not contain organization.")
        self.slug = slug


class TestLiveHandler(TestCase):
    """
    Tests requiring a real GitHub connection.
    It needs `github_token` to be defined in
    `chevah/github_hooks_server/tests/private.py`.
    """
    def setUp(self):
        super(TestLiveHandler, self).setUp()
        self.handler = Handler(
            github3.login(token=github_token), config=config
            )

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
# The creator of the PR (and review-requester) is adiroiban,
# and the reviewers are danuker and/or chevah-robot.

    def prepareToNeedReview(self):
        """
        Prepare the PR so that it will need review.

        Assigned is none of the reviewers and PR has other labels.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-changes', 'needs-merge', 'low'])
        issue.edit(assignees=['adiroiban'])
        pr = issue.pull_request()
        pr.delete_review_requests(
            reviewers=pr.requested_reviewers,
            team_reviewers=pr.requested_teams,
            )
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('needs-merge', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-review', initial_labels)
        self.assertEqual(['adiroiban'], [u.login for u in issue.assignees])
        # Must retrieve the requested reviewers again, in order to check them.
        self.assertEqual(
            [], [u.login for u in issue.pull_request().requested_reviewers]
            )
        return issue, pr

    def assertReviewRequested(self, from_users=None, from_teams=None):
        """
        Check that the review was requested for the PR.

        Label is needs-review, and review requests are created.
        The assignees are left alone.

        `from_teams` contains just the slugs of the teams,
        without the organization.
        Example: ["the-b-team"], not ["chevah/the-b-team"].
        """
        if from_users is None:
            from_users = ['danuker', 'chevah-robot']
        if from_teams is None:
            from_teams = []
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-changes', last_labels)
        self.assertNotIn('needs-merge', last_labels)
        self.assertEqual(['adiroiban'], [u.login for u in issue.assignees])
        self.assertCountEqual(
            from_users,
            [u.login for u in issue.pull_request().requested_reviewers])
        self.assertCountEqual(
            from_teams,
            [t.slug for t in issue.pull_request().requested_teams])

    def test_issue_comment_needs_review(self):
        """
        A needs review request is sent to a PR if comment body contains
        **needs-review** marker and other review labels are removed.
        """
        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nreviewers @danuker @chevah-robot\r\nbla',
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
            "reviewers=['danuker', 'chevah-robot']"
            )
        self.assertReviewRequested()

    def test_issue_comment_needs_review_team(self):
        """
        Sets "needs-review" label and assigns the team for review,
        when a review is asked for, via a comment.

        The team is requested because the default reviewer is configured to be
        the team in `tests/test_config.ini`.
        """

        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nbla',
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
            "reviewers=['chevah/the-b-team']"
            )
        self.assertReviewRequested(from_users=[], from_teams=['the-b-team'])

    def test_review_requested_needs_review(self):
        """
        When a review is requested from someone,
        and there is a reviewers list in the PR description,
        the "needs-review" action is also triggered.

        There are two relevant actions under the `pull_request` event:
        `review_requested` and `ready_for_review`.
        https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#pull_request
        """
        actions = ['review_requested', 'ready_for_review']

        for action in actions:
            requested_reviewers = []
            if action == 'review_requested':
                requested_reviewers = [
                    StubUser('danuker'), {'login': 'chevah-robot'},
                    ]

            content = {
                'action': action,
                'pull_request': {
                    'html_url': 'something',
                    'title': '[#12] Some message.',
                    'body': 'bla\r\nreviewers @danuker @chevah-robot\r\nbla',
                    'number': 8,
                    'user': {'login': 'adiroiban'},
                    'requested_reviewers': requested_reviewers,
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
                "reviewers=['danuker', 'chevah-robot']"
                )

        self.assertReviewRequested()

    def test_review_requested_without_reviewers_in_description(self):
        """
        When a user requests a review,
        but the PR description does not have a reviewer list,
        the "needs-review" label is set.

        Does not automatically ask for any other review, because:
        1. the requester has the ability to request reviews
            (because the action is `review_requested`)
        2. it is assumed the requester selected everyone they need.

        Does not delete pre-existing review requests (here, for danuker).
        """
        content = {
            'action': 'review_requested',
            'pull_request': {
                'html_url': 'something',
                'title': '[#12] Some message.',
                'body': 'bla\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                'requested_reviewers': [StubUser('danuker')],
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }

        issue, stale_pr = self.prepareToNeedReview()
        stale_pr.create_review_requests(['danuker'])

        event = Event(name='pull_request', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            "_setNeedsReview "
            "event=pull_request, "
            "repo=chevah/github-hooks-server, "
            "pull_id=8, "
            "reviewers=['danuker']"
            )
        self.assertReviewRequested(from_users=['danuker'])

    def test_needs_review_nonexistent_user(self):
        """
        When a reviewer can not be asked to review,
        the labels are still set.
        """
        body = u'One more r\xc9sume\r\n\r\n**needs-review**\r\n'
        content = {
            u'issue': {
                u'pull_request': {u'html_url': u'something'},
                u'title': u'[#12] Some message.',
                u'body': u'bla\r\nreviewers @nonexistent_user\r\nbla',
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
            "reviewers=['nonexistent_user']"
            )
        self.assertReviewRequested(from_users=[])

    def test_pull_request_review_comment_asking_for_review(self):
        """
        Labels and reviewers are set
        when a review is requested via a PR review comment.
        """
        body = u'Please review this PR.'
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                u'body': u'bla\r\nreviewers @danuker @chevah-robot\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                'requested_reviewers': [],
                'requested_teams': [],
                },
            'review': {
                'user': {'login': 'adiroiban'},
                'body': body,
                'state': 'commented',
                },
            'repository': {
                'full_name': 'chevah/github-hooks-server',
                },
            }

        self.prepareToNeedReview()
        event = Event(name='pull_request_review', content=content)

        self.handler.dispatch(event)

        self.assertLog(
            "_setNeedsReview "
            "event=pull_request_review, "
            "repo=chevah/github-hooks-server, "
            "pull_id=8, "
            "reviewers=['danuker', 'chevah-robot']"
            )
        self.assertReviewRequested()

#
# --------------------- needs-changes -----------------------------------------
#
    def prepareToRequestChanges(self, from_reviewers=None, from_teams=None):
        """
        Set up the PR so that we can request changes.

        PR doesn't have the author as assignee and has the needs-review label.
        """
        if from_reviewers is None:
            from_reviewers = ['chevah-robot']
        if from_teams is None:
            from_teams = ['the-b-team']

        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-merge', 'low'])
        issue.edit(assignees=['chevah-robot'])
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-merge', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-changes', initial_labels)
        self.assertEqual(['chevah-robot'], [u.login for u in issue.assignees])
        issue.pull_request().create_review_requests(
            reviewers=from_reviewers, team_reviewers=from_teams
            )

    def assertChangesRequested(self):
        """
        Check that the request changes was done for PR.

        Label is needs-changes and author is set at assignee.
        Review requests are emptied.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-changes', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-review', last_labels)
        self.assertNotIn('needs-merge', last_labels)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])
        self.assertCountEqual([], issue.pull_request().requested_reviewers)
        self.assertCountEqual([], issue.pull_request().requested_teams)

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
        in the needs-changes state, and any other review requests are removed.
        """
        self.prepareToRequestChanges()
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nbla',
                'user': {'login': 'adiroiban'},
                'number': 8,
                'requested_reviewers': [{'login': 'ioanacristinamarinescu'}],
                'requested_teams': [],
                },
            'review': {
                'user': {'login': 'chevah-robot'},
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

        Only one review is requested, the reviewer is assigned,
        and label is not needs-merge.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        pr = issue.pull_request()
        pr.delete_review_requests(
            reviewers=pr.requested_reviewers,
            team_reviewers=pr.requested_teams,
            )
        pr.create_review_requests(['chevah-robot'])
        issue.edit(assignees=['adiroiban'])
        issue.replace_labels(['needs-review', 'needs-changes', 'low'])
        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-merge', initial_labels)
        self.assertEqual(['adiroiban'], [u.login for u in issue.assignees])
        return pr

    def assertMergeRequested(self):
        """
        Check that merge was requested for the PR.

        Label is needs-merge and author is set as assignee.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-merge', last_labels)
        self.assertIn('low', last_labels)
        self.assertNotIn('needs-review', last_labels)
        self.assertNotIn('needs-changes', last_labels)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in issue.assignees])

        # No more review requests.
        pr = issue.pull_request()
        self.assertCountEqual(
            [], [u.login for u in pr.requested_reviewers])

    def test_issue_comment_approved_last(self):
        """
        A needs-merge request is sent to PR
        if body contains the `changes-approved` marker,
        and the user is the last reviewer (no others in `remaining_reviewers`).
        """
        self.prepareToApproveLast()
        content = {
            'issue': {
                'pull_request': {u'html_url': u'something'},
                'title': '[#12] Some message r\xc9sume.',
                'body': (
                    'r\xc9sume bla\r\n'
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
            "reviewer_name=chevah-robot, "
            "remaining_reviewers=[]"
            )
        self.assertMergeRequested()

    def test_pull_request_review_approved_last(self):
        """
        When the review was approved and no other reviewers are expected,
        the PR is set into the needs-merge state.
        """
        pr = self.prepareToApproveLast()

        # A user submits a review.
        pr.delete_review_requests(['chevah-robot'])

        # And GitHub sends us an API call in consequence.
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                'requested_reviewers': [],
                'requested_teams': [],
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
            'reviewer_name=chevah-robot, '
            "remaining_reviewers=[]"
            )
        self.assertMergeRequested()

#
# --------------------- changes-approved -> still left to review --------------
#
    def prepareToApproveAndLeaveForReview(self):
        """
        Set up the PR so that we can approve the changes
        and other reviewers still need to review it.
        """
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        issue.replace_labels(['needs-review', 'needs-changes', 'low'])
        issue.edit(assignees=['adiroiban'])

        # Create review requests for two people.
        pr = issue.pull_request()
        pr.delete_review_requests(
            reviewers=pr.requested_reviewers,
            team_reviewers=pr.requested_teams,
            )
        pr.create_review_requests(['chevah-robot', 'danuker'])

        initial_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', initial_labels)
        self.assertIn('needs-changes', initial_labels)
        self.assertIn('low', initial_labels)
        self.assertNotIn('needs-merge', initial_labels)
        self.assertCountEqual(
            ['adiroiban'], [u.login for u in pr.assignees])
        return pr

    def assertReviewStillNeeded(self, from_users=None, from_teams=None):
        """
        Check that review is still needed for the PR, after the first approval.
        The assignees are left alone.

        `from_teams` contains just the slugs of the teams,
        without the organization.
        Example: ["the-b-team"], not ["chevah/the-b-team"].
        """
        if from_users is None:
            from_users = ['chevah-robot']
        if from_teams is None:
            from_teams = []
        issue = self.handler._github.issue('chevah', 'github-hooks-server', 8)
        last_labels = [l.name for l in issue.labels()]
        self.assertIn('needs-review', last_labels)
        self.assertIn('low', last_labels)
        self.assertIn('needs-changes', last_labels)
        self.assertEqual(
            ['adiroiban'], [u.login for u in issue.assignees])
        self.assertCountEqual(
            from_users,
            [u.login for u in issue.pull_request().requested_reviewers])
        self.assertCountEqual(
            from_teams,
            [t.slug for t in issue.pull_request().requested_teams])

    def test_issue_comment_approved_still_reviewers(self):
        """
        When body contains the `changes-approved` marker and there are still
        reviewers, the PR is kept in the same state.
        """
        self.prepareToApproveAndLeaveForReview()
        content = {
            'issue': {
                'pull_request': {'html_url': 'something'},
                'title': '[#12] Some message.',
                'body': 'bla\r\nbla',
                'number': 8,
                'user': {'login': 'adiroiban'},
                },
            'comment': {
                'user': {'login': 'danuker'},
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
            "reviewer_name=danuker, "
            "remaining_reviewers=['chevah-robot']"
            )
        self.assertReviewStillNeeded()

    def test_issue_comment_approved_still_reviewers_team(self):
        """
        When body contains the `changes-approved` marker
        and there are still team reviewers requested,
        the PR is kept in the same state.
        """
        pr = self.prepareToApproveAndLeaveForReview()

        # A team review is requested.
        pr.create_review_requests(team_reviewers=['the-b-team'])

        # The users submitted reviews. Only the team remains.
        pr.delete_review_requests(['danuker', 'chevah-robot'])

        # And GitHub sends us an API call in consequence.
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nbla',
                'number': 8,
                'user': {'login': 'pr-author-ignored'},
                'requested_reviewers': [],
                'requested_teams': [StubTeam('the-b-team')]
                },
            'review': {
                'user': {'login': 'danuker'},
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
            'reviewer_name=danuker, '
            "remaining_reviewers=['chevah/the-b-team']"
            )
        self.assertReviewStillNeeded(from_users=[], from_teams=['the-b-team'])

    def test_pull_request_review_approved_still_reviewers(self):
        """
        When the review was approved and there are other reviewers,
        the PR is left in needs-review and reviewer is removed.
        """
        pr = self.prepareToApproveAndLeaveForReview()

        # A user submits a review.
        pr.delete_review_requests(['danuker'])

        # And GitHub sends us an API call in consequence.
        content = {
            'pull_request': {
                'title': '[#42] Some message.',
                'body': 'bla\r\nbla',
                'number': 8,
                'user': {'login': 'pr-author-ignored'},
                'requested_reviewers': [StubUser('chevah-robot')],
                'requested_teams': [],
                },
            'review': {
                'user': {'login': 'danuker'},
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
            'reviewer_name=danuker, '
            "remaining_reviewers=['chevah-robot']"
            )
        self.assertReviewStillNeeded()

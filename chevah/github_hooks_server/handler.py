"""
Custom logic for handling GitHub hooks.
"""
import logging
import re

import github3


class Handler(object):
    """
    Handles github hooks.

    Should implement a method with the same name as github event.
    """

    USERS_GITHUB_TO_TRAC = {
        'adiroiban': 'adi',
        'lgheorghiu': 'laura',
        'hcs0': 'hcs',
        }

    RE_TRAC_TICKET_ID = r'\[#(\d+)\] .*'
    RE_REVIEWERS = r'.*reviewers{0,1}:{0,1} @.*'
    RE_NEEDS_REVIEW = r'.*needs{0,1}[\-_]review.*'
    RE_NEEDS_CHANGES = r'.*needs{0,1}[\-_]changes{0,1}.*'
    RE_APPROVED = r'.*(changes{0,1}[\-_]approved{0,1})|(approved-at).*'

    def __init__(self, trac_url, github):
        self._github = github
        if not self._github:
            raise RuntimeError('Failed to init GitHut.')

    def dispatch(self, event):
        """
        Main event dispatcher.
        """
        handler = getattr(self, event.name, None)
        if handler is None:
            message = f'No handler for "{event.name}"'
            logging.error(message)
            return message

        return handler(event)

    def ping(self, event):
        """
        Called when GitHub sends us a ping.
        """
        logging.info('Serving a POST ping.')
        zen = event.content.get('zen')
        if not zen:
            return 'Pong! But GitHub Zen text is missing.'
        return f'Pong! {zen}'

    def pull_request_review(self, event):
        """
        Called when a PR review overview message is left.
        """
        if event.content.get('action', 'submitted') != 'submitted':
            logging.info('[%s] Not review submission.' % (event.name))
            return

        title = event.content['pull_request']['title']
        ticket_id = self._getTicketFromTitle(title)

        state = event.content['review']['state']
        repo = event.content['repository']['full_name']
        issue_id = event.content['pull_request']['number']
        author_name = event.content['pull_request']['user']['login']
        body = event.content['review']['body']
        reviewer_name = self._getTracUser(
            event.content['review']['user']['login'])

        reviewers = self._getReviewers(event.content['pull_request']['body'])

        logging.info(u'[%s][%s] New review from %s as %s\n%s' % (
            event.name, ticket_id, reviewer_name, state, body))

        if state == 'approved':
            # An approved review comment.
            self._setApproveChanges(
                repo, ticket_id, issue_id, author_name, reviewer_name, body,
                reviewers,
                )
        elif state == 'changes_requested':
            # An needs changes review comment.
            self._setNeedsChanges(
                repo, ticket_id, issue_id, author_name, reviewer_name, body)
        else:
            # Just a simple comment.
            # Do nothing
            return

    def _removeLabels(self, issue, labels):
        """
        Remove labels from the issue, if they exist.
        """
        for label in labels:
            try:
                issue.remove_label(label)
            except github3.exceptions.NotFoundError:
                """
                Label did not exist. Move on.
                """

    def _setNeedsReview(
            self, repo, ticket_id, issue_id, user, body, reviewers, pull_url):
        """
        Set the ticket to needs review.
        """
        logging.debug(
            f'_setNeedsReview '
            f'repo={repo}, issue_id={issue_id}, reviewers={reviewers}')

        # Do the GitHub stuff
        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, issue_id)
        if issue:
            issue.add_labels('needs-review')
            self._removeLabels(issue, ['needs-changes', 'needs-merge'])
            gh_users = [self._getGitHubUser(r) for r in reviewers]
            issue.edit(assignees=gh_users)
        else:
            logging.error('Failed to get PR %s for %s' % (issue_id, repo))

    def _setNeedsChanges(
            self, repo, ticket_id, issue_id, author_name, reviewer_name, body):
        """
        Set the ticket with `ticket_id` in needs changes state.
        """
        # Do the GitHub stuff
        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, issue_id)
        if issue:
            issue.add_labels('needs-changes')
            self._removeLabels(issue, ['needs-review', 'needs-merge'])
            issue.edit(assignees=[author_name])
        else:
            logging.error('Failed to get PR %s for %s' % (issue_id, repo))

    def _setApproveChanges(
            self, repo, ticket_id, issue_id, author_name, reviewer_name, body,
            reviewers,
            ):
        """
        Update the ticket with `ticket_id` as approved.
        """
        # Do the GitHub stuff
        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, issue_id)

        if issue:
            current_reviewers = set([u.login for u in issue.assignees])
            remaining_reviewers = (
                current_reviewers -
                set([self._getGitHubUser(reviewer_name)])
                )

            if not remaining_reviewers:
                # All reviewers done
                issue.add_labels('needs-merge')
                self._removeLabels(issue, ['needs-review', 'needs-changes'])
                issue.edit(assignees=[author_name])
            else:
                issue.edit(assignees=list(remaining_reviewers))

        else:
            logging.error('Failed to get PR %s for %s' % (issue_id, repo))

    def issue_comment(self, event):
        """
        At comments on issues which are pull request, check for
        command and sync state with trac.
        """
        if event.content.get('action', 'created') != 'created':
            logging.error('[%s] Not a created issue comment.' % (event.name))
            return

        pull_url = event.content['issue']['pull_request']['html_url']
        if not pull_url:
            logging.error(
                '[%s] Not a comment on a pull request' % (event.name)
                )
            return

        repo = event.content['repository']['full_name']
        issue_id = event.content['issue']['number']

        message = event.content['issue']['title']
        ticket_id = self._getTicketFromTitle(message)

        body = event.content['comment']['body']
        reviewer_name = self._getTracUser(
            event.content['comment']['user']['login'])

        author_name = event.content['issue']['user']['login']

        reviewers = self._getReviewers(event.content['issue']['body'])

        logging.info(u'[%s][%s] New comment from %s with reviewers %s\n%s' % (
            event.name, ticket_id, reviewer_name, reviewers, body))

        if self._needsReview(body):
            self._setNeedsReview(
                repo, ticket_id, issue_id, reviewer_name, body, reviewers,
                pull_url,
                )

        elif self._needsChanges(body):
            self._setNeedsChanges(
                repo, ticket_id, issue_id, author_name, reviewer_name, body)

        elif self._changesApproved(body):
            self._setApproveChanges(
                repo, ticket_id, issue_id, author_name, reviewer_name, body,
                reviewers,
                )

    def _getTicketFromTitle(self, text):
        """
        Parse title and return ticket id or None if text
        does not contains a ticket id.
        """
        # https://github.com/chevah/seesaw/pull/12-some.new
        result = re.match(self.RE_TRAC_TICKET_ID, text)
        if not result:
            logging.error(
                'Pull request has no ticket id in title: %s' % (text,))
            return
        return int(result.group(1))

    def _getReviewers(self, message):
        """
        Return the list of reviewers as Trac names.
        """
        results = self._getGitHubReviewers(message)

        # Convert to Trac accounts... if we can.
        reviewers = []
        for git_login in results:
            trac_login = self._getTracUser(git_login)
            reviewers.append(trac_login)
        return reviewers

    def _getGitHubReviewers(self, message):
        """
        Return the list of reviewers as GitHub names.
        """
        results = []
        for line in message.splitlines():
            result = re.match(self.RE_REVIEWERS, line)
            if not result:
                continue
            for word in line.split(' '):
                if word.startswith('@'):
                    results.append(word[1:].strip())
        return results

    def _getTracUser(self, git_login):
        """
        Return the Trac account associated for Git login.
        """
        try:
            return self.USERS_GITHUB_TO_TRAC[git_login]
        except KeyError:
            return git_login

    def _getGitHubUser(self, trac_login):
        """
        Return the GitHub ID based on trac ID.
        """
        for key, value in self.USERS_GITHUB_TO_TRAC.items():
            if value.lower() == trac_login.lower():
                return key
        return trac_login

    def _needsChanges(self, content):
        """
        Return True if content has the needs-changes marker.
        """
        for line in content.splitlines():
            result = re.match(self.RE_NEEDS_CHANGES, line)
            if result:
                return True
        return False

    def _needsReview(self, content):
        """
        Return True if content has the needs-review marker.
        """
        for line in content.splitlines():
            result = re.match(self.RE_NEEDS_REVIEW, line)
            if result:
                return True
        return False

    def _changesApproved(self, content):
        """
        Return True if content has the approved-changes marker.
        """
        for line in content.splitlines():
            result = re.match(self.RE_APPROVED, line)
            if result:
                return True
        return False

    def _getRemainingReviewers(self, cc_string, user):
        """
        Remove user from cc list and  return the remaining list of
        reviewers.
        """
        reviewers = []
        for review in cc_string.split(','):
            reviewers.append(review.strip())
        try:
            reviewers.remove(user)
        except ValueError:
            logging.error(
                'Current user "%s" not in the list of reviewers %s' % (
                    user, cc_string))
        return reviewers

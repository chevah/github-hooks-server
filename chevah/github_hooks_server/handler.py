"""
Custom logic for handling GitHub hooks.
"""
import logging
import re

import github3
from github3.exceptions import UnprocessableEntity


class HandlerException(Exception):
    """
    Generic handler exception.
    """
    def __init__(self, message):
        self.message = message


class Handler(object):
    """
    Handles github hooks.

    Should implement a method with the same name as github event.
    """

    RE_TRAC_TICKET_ID = r'\[#(\d+)\] .*'
    RE_REVIEWERS = r'.*reviewers{0,1}:{0,1} @.*'
    RE_NEEDS_REVIEW = r'.*needs{0,1}[\-_]review.*'
    RE_NEEDS_REVIEW_TWISTED = r'.*(please[ \-]review|review[ \-]please).*'
    RE_NEEDS_CHANGES = r'.*needs{0,1}[\-_]changes{0,1}.*'
    RE_APPROVED = r'.*(changes{0,1}[\-_]approved{0,1})|(approved-at).*'

    def __init__(self, github, config):
        self._github = github
        self._config = config
        if not self._github:
            raise RuntimeError('Failed to init GitHub.')

    def dispatch(self, event):
        """
        Main event dispatcher.
        """
        handler = getattr(self, event.name, None)
        if handler is None:
            message = f'No handler for "{event.name}"'
            logging.debug(message)
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

    def pull_request(self, event):
        """
        Called for actions on a PR, except the actions done by a reviewer.

        See: https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#pull_request
        """
        action = event.content.get('action')
        if action not in ['review_requested', 'ready_for_review']:
            logging.debug(f"No handler for pull_request action '{action}'.")
            return

        repo = event.content['repository']['full_name']
        pull_id = event.content['pull_request']['number']
        message = event.content['pull_request']['body']
        requested_reviewers = [
            u.login
            for u in event.content['pull_request']['requested_reviewers']
            ]
        if not requested_reviewers:
            requested_reviewers = self._getReviewers(
                message=message,
                repo=repo,
                action=action,
                )

        self._raiseIfShouldSkip(repo, pull_id)

        self._setNeedsReview(
            repo=repo,
            pull_id=pull_id,
            reviewers=requested_reviewers,
            event=event
            )

    def pull_request_review(self, event):
        """
        Called when a "PR Review" action is made.

        For example, when approving or rejecting a PR via a review.

        See https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#pull_request_review
        """
        if event.content.get('action', 'submitted') != 'submitted':
            logging.info('[%s] Not review submission.' % (event.name))
            return

        state = event.content['review']['state']
        repo = event.content['repository']['full_name']
        pull_id = event.content['pull_request']['number']
        author_name = event.content['pull_request']['user']['login']
        reviewer_name = event.content['review']['user']['login']
        remaining_reviewers = [
            u.login
            for u in event.content['pull_request']['requested_reviewers']
            ]

        self._raiseIfShouldSkip(repo, pull_id)

        if state == 'approved':
            # An approved review comment.
            self._setApproveChanges(
                repo=repo,
                pull_id=pull_id,
                author_name=author_name,
                reviewer_name=reviewer_name,
                remaining_reviewers=remaining_reviewers,
                event=event,
                )
        elif state == 'changes_requested':
            # An needs changes review comment.
            self._setNeedsChanges(
                repo=repo,
                pull_id=pull_id,
                author_name=author_name,
                event=event,
                )
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

    def _setNeedsReview(self, repo, pull_id, reviewers, event):
        """
        Set the PR to needs review.
        """
        logging.debug(
            f'_setNeedsReview '
            f'event={event.name}, '
            f'repo={repo}, '
            f'pull_id={pull_id}, '
            f'reviewers={reviewers}'
            )

        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, pull_id)
        if issue:
            issue.add_labels('needs-review')
            self._removeLabels(issue, ['needs-changes', 'needs-merge'])
            issue.pull_request().create_review_requests(reviewers)
        else:
            logging.error('Failed to get PR %s for %s' % (pull_id, repo))

    def _setNeedsChanges(self, repo, pull_id, author_name, event):
        """
        Set the PR with `pull_id` in needs changes state.
        """
        logging.debug(
            f'_setNeedsChanges '
            f'event={event.name}, '
            f'repo={repo}, '
            f'pull_id={pull_id}, '
            f'author_name={author_name}'
            )

        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, pull_id)
        if issue:
            issue.add_labels('needs-changes')
            self._removeLabels(issue, ['needs-review', 'needs-merge'])
            pr = issue.pull_request()
            pr.delete_review_requests(pr.requested_reviewers)
            issue.edit(assignees=[author_name])
        else:
            logging.error('Failed to get PR %s for %s' % (pull_id, repo))

    def _setApproveChanges(
            self,
            repo,
            pull_id,
            author_name,
            reviewer_name,
            remaining_reviewers,
            event):
        """
        Update the PR with `pull_id` as approved.
        """
        logging.debug(
            f'_setApproveChanges '
            f'event={event.name}, '
            f'repo={repo}, '
            f'pull_id={pull_id}, '
            f'author_name={author_name}, '
            f'reviewer_name={reviewer_name}, '
            f'remaining_reviewers={remaining_reviewers}'
            )

        username, repository = repo.split('/', 1)
        issue = self._github.issue(username, repository, pull_id)
        if issue:
            if not remaining_reviewers:
                # All reviewers done
                issue.add_labels('needs-merge')
                self._removeLabels(issue, ['needs-review', 'needs-changes'])
                issue.edit(assignees=[author_name])
        else:
            logging.error('Failed to get PR %s for %s' % (pull_id, repo))

    def issue_comment(self, event):
        """
        Look for a command in comments on pull requests,
        and perform the command.
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
        pull_id = event.content['issue']['number']

        self._raiseIfShouldSkip(repo, pull_id)

        body = event.content['comment']['body']
        reviewer_name = event.content['comment']['user']['login']

        author_name = event.content['issue']['user']['login']

        reviewers = self._getReviewersFromMessage(
            message=event.content['issue']['body']
            )

        if self._needsReview(body):
            self._setNeedsReview(
                repo=repo, pull_id=pull_id, reviewers=reviewers, event=event
                )

        elif self._needsChanges(body):
            self._setNeedsChanges(
                repo=repo,
                pull_id=pull_id,
                author_name=author_name,
                event=event,
                )

        elif self._changesApproved(body):
            # We only need to delete the review request
            # when the reviewer made a "regular" comment,
            # without creating a GitHub review.
            username, repository = repo.split('/', 1)
            pull = self._github.pull_request(username, repository, pull_id)
            pull.delete_review_requests([reviewer_name])

            # The PR model does not update the `requested_reviewers`
            # after deleting the review request,
            # so we have to manually remove it.
            remaining_reviewers = list(
                set(u.login for u in pull.requested_reviewers) -
                {reviewer_name}
                )

            self._setApproveChanges(
                repo=repo,
                pull_id=pull_id,
                author_name=author_name,
                reviewer_name=reviewer_name,
                remaining_reviewers=remaining_reviewers,
                event=event,
                )

    def _getReviewers(self, message, repo, action):
        """
        Identifies the accounts to request reviews from.

        If a user manually requested a review ('review_requested' action),
        and did not specify reviewers in the PR description,
        do not request any other reviews.

        Possible actions are specified in the `pull_request` method.
        """
        reviewers = self._getReviewersFromMessage(message)

        if not reviewers and action != 'review_requested':
            reviewers = self._getDefaultReviewers(repo=repo)
        return reviewers

    def _getReviewersFromMessage(self, message):
        """
        Return the list of reviewers mentioned in the given text message
        (a PR description).
        """
        results = []
        if not message:
            return results

        for line in message.splitlines():
            result = re.match(self.RE_REVIEWERS, line)
            if not result:
                continue
            for word in line.split(' '):
                if word.startswith('@'):
                    results.append(word[1:].strip())
        return results

    def _getDefaultReviewers(self, repo):
        """
        Returns the list of default reviewers configured for a repo.
        If none is configured, returns empty list.
        """
        reviewers = self._config.get('default-reviewers', {}).get(repo, [])

        if not reviewers:
            # We have no default reviewers for the repository.
            # Look for default organization reviewers.
            org = repo.split('/')[0] + '/'
            reviewers = self._config.get('default-reviewers', {}).get(org, [])

        return reviewers

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
            if re.match(self.RE_NEEDS_REVIEW, line):
                return True
            if re.match(self.RE_NEEDS_REVIEW_TWISTED, line):
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

    def _shouldHandlePull(self, repo, number):
        """
        Return True if we should handle this pull request.
        """
        repos = self._config['skip'].split(',')
        print(repos)
        if repo in repos:
            return False
        if f'{repo}#{number}' in repos:
            return False
        return True

    def _raiseIfShouldSkip(self, repo, number):
        """
        Raise a HandlerException if we should skip this PR.
        """
        if not self._shouldHandlePull(repo, number):
            raise HandlerException(f'Skipping {repo}#{number}.')

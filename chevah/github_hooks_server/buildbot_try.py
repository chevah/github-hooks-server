"""
Changes of the upstream github_buildbot.

The upstream code uses the PB change source, while we are using the
try scheduler.
"""
from __future__ import absolute_import
from __future__ import print_function

import json
import logging
import httplib

from twisted.internet import defer

from chevah.github_hooks_server.github_buildbot import GitHubBuildBot


# Name of the repos which will not trigger tests on PR push.
PR_EXCEPTED_REPOS = [
    'chevah/python-package',
    ]


class BuildbotTryNotifier(GitHubBuildBot):
    """
    Instead of sending to PBChangeSource it send to the try scheduler.
    """

    def __init__(self, configuration):
        # See github_buildbot.run_hook()
        self.github = configuration['github-server']
        self.secret = configuration['github-hook-secret']

        self.master = configuration['buildbot-master']
        self.auth = configuration['buildbot-credentials']

        self.head_commit = False

    def handle_pull_request(self, payload, repo, repo_url):
        """
        Consumes the JSON as a python object and actually starts the build.

        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        if repo in PR_EXCEPTED_REPOS:
            return None

        if payload['action'] not in ("opened", "synchronize"):
            logging.info(
                "PR %r %r, ignoring", payload['number'], payload['action'])
            return None

        branch = payload['pull_request']['head']['ref']
        # Create the base change.
        change = {
            'id': payload['pull_request']['head']['sha'],
            'message': payload['pull_request']['title'],
            'timestamp': payload['pull_request']['updated_at'],
            'url': payload['pull_request']['html_url'],
            'author': {
                'username': payload['pull_request']['user']['login'],
            },
            'added': [],
            'removed': [],
            'modified': [],
        }
        return [self.process_change(change, branch, repo, repo_url)]

    def process_change(self, change, branch, repo, repo_url):
        """
        Gather changes from various sources and produce a single structure.
        """
        files = change['added'] + change['removed'] + change['modified']
        who = ""
        if 'username' in change['author']:
            who = change['author']['username']
        else:
            who = change['author']['name']

        if 'email' in change['author']:
            who = "%s <%s>" % (who, change['author']['email'])

        comments = 'GitHub Hooks: %s' % (change['message'],)
        if len(comments) > 128:
            trim = " ... (trimmed)"
            comments = comments[:128 - len(trim)] + trim

        properties = {}

        if '/pull/' in change['url']:
            pr_id = change['url'].rsplit('/', 1)[1]
            # We have a PR change.
            properties['github_pull_id'] = pr_id
        else:
            pr_id = None

        project = repo.split('/')[1]

        return {
            'revision': change['id'],
            'revlink': change['url'],
            'who': who,
            'properties': properties,
            'pr': pr_id,
            'comments': comments,
            'repository': repo_url,
            'files': files,
            'project': project,
            'slug': repo,
            'branch': branch,
            }

    def connected(self, remote, changes, request):
        """
        Called when we are connected to the PR.
        """
        # By this point we've connected to buildbot so
        # we don't really need to keep github waiting any
        # longer
        request.setResponseCode(httplib.ACCEPTED)
        request.write(json.dumps({"result": "Submitting changes."}))
        request.finish()
        return self.addChange(remote, changes.__iter__())

    def addChange(self, remote, changei):
        """
        Sends changes from the commit to the buildmaster.
        """
        try:
            change = changei.next()
        except StopIteration:
            remote.broker.transport.loseConnection()
            return None

        logging.info("New revision: %s", change['revision'][:8])
        for key, value in change.items():
            logging.debug("  %s: %s", key, value)

        if change['branch'] == 'master' or change['pr'] is not None:
            # Only trigger if it was pushed on master or PR.
            deferred = remote.callRemote(
                'try',
                branch=change['branch'],
                revision=change['revision'],
                project=change['project'],
                repository=change['repository'],
                who=change['who'],
                comment=change['comments'],
                properties=change['properties'],
                # Try specific changes.
                patch=(1, ''),
                builderNames=['%s-gk-review' % (change['project'],)],
                )
        else:
            deferred = defer.succeed(None)
            logging.debug('Ignoring change as not pushed to master or PR.')

        deferred.addCallback(lambda _: self.addChange(remote, changei))
        return deferred

"""
Changes of the upstream github_buildbot.
"""
from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

import logging

from twisted.internet import defer

from chevah.github_hooks_server.github_buildbot import GitHubBuildBot



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
        self.category = None

    def addChange(self, _, remote, changei, src='git'):
        """
        Sends changes from the commit to the buildmaster.
        """
        logging.debug("addChange %r, %r", remote, changei)
        try:
            change = changei.next()
        except StopIteration:
            remote.broker.transport.loseConnection()
            return None

        logging.info("New revision: %s", change['revision'][:8])
        for key, value in iteritems(change):
            logging.debug("  %s: %s", key, value)

        properties = {}
        project = change['project'].split('/')[1]

        if '/pull/' in change['revlink']:
            # We have a PR change.
            properties = {
                'github_pull_id': change['revlink'].rsplit('/', 1)[1],
                }

        if change['branch'] == 'master' or properties:
            # Only trigger if it was pushed on master or PR.
            deferred = remote.callRemote(
                'try',
                branch=change['branch'],
                revision=change['revision'],
                patch=(1, ''),
                project='project',
                repository=change['repository'],
                builderNames=['%s-gk-review' % (project,)],
                who=change['who'],
                comment="GitHub Hooks: %s" % (change['comments'],),
                properties=properties,
                )
        else:
            deferred = defer.succeed(None)
            logging.debug('Ignoring change as not pushed to master or PR.')

        deferred.addCallback(self.addChange, remote, changei, src)
        return deferred

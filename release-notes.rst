0.9.1 (2017-11-13)
==================

* Fix GitHub token when not set. Use None instead of empty string for internal
  handling.


0.9.0 (2017-11-12)
==================

* Add configuration file.
* Allow changing the review workflow for PR without a Trac ticket.



0.8.3 (2017-11-02)
==================

* Update Bruno's handle.


0.8.2 (2017-10-04)
==================

* Add a log when failing to fetch the issue.
* Only trigger on review requests and comment creation. Not on edit, delete,
  dismiss.


0.8.1 (2017-10-04)
==================

* Declare missing github3.py dependencies in our setup.py


0.8.0 (2017-10-04)
==================

* Manage labels on GitHub to get some review state.
* Ignore delete events.
* Remove dependency to future.


0.7.2 (2017-08-04)
==================

* Ignore `python-package` from PR auto-tests.


0.7.1 (2017-06-12)
==================

* Fix the branch named send by try for a PR via GitHub hooks.


0.7.0 (2017-06-12)
==================

* Send GitHub hooks to Buildbot via try scheduler.


0.6.1 (2017-05-16)
==================

* Add separate configuration module, which should be imported first.


0.6.0 (2017-05-15)
==================

* Make GitHub Review comments to use a format friendly to Leaderboard.
* Remove highscores.
* Remove dependency on txghserf.


0.5.4 (2017-04-18)
==================

* Add total info.


0.5.3 (2017-04-18)
==================

* Remove future unicode_literals.


0.5.2 (2017-04-18)
==================

* Fix bytes/unicode for response.


0.5.1 (2017-04-18)
==================

* Remove dependency on epsilon.


0.5.0 (2017-04-18)
==================

* Add support for highscores based on Trac.


0.4.1 (2016-12-02)
==================

* Add alias for Hannah.


0.3.8 (2015-03-05)
==================

* Clean handler registration, again.


0.3.7 (2015-03-05)
==================

* Clean handler registration.


0.3.6 (2015-03-05)
==================

* Fix typo in handler registration.


0.3.5 (2015-03-05)
==================

* Fix event handler registration.


0.3.4 (2015-03-05)
==================

* Don't run as daemon by default.


0.3.3 (2015-03-05)
==================

* Keep backward compatiblity with old `approved-at` marker.


0.3.2 (2015-03-05)
==================

* Add option to start server with a pid file.


0.3.1 (2015-03-05)
==================

* Log Trac errors.


0.3.0 (2015-03-05)
==================

* Update Trac password.


0.2.4 (2014-04-17)
==================

* Update Trac password.


0.2.3 (2013-12-22)
==================

* Fix port for Trac server.


0.2.2 (2013-12-22)
==================

* Use Trac dedicated IP address.


0.2.1 (2013-10-05)
==================

* Fix logging of unicode text.
* Add need-review and require-changes as valid markers.


0.2.0 (2013-04-07)
==================

* Update the new Trac ticket workflow.
* Append comment to Trac ticket for GitHub review actions.

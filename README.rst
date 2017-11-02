github-hooks-server
===================

Custom handling of GitHub hooks for Chevah Project.

It keeps Trac and GitHub in sync based on Chevah's own workflow.

It manages the labels for a PR to keep track of the review state for a PR.

The GitHub Token needs to have write permissions to the managed repo.

The code is public but the package is private.
It is not / and should not be published on PyPi.

Also tests are designed to run from Chevah VPN with access to staging Trac
instance.

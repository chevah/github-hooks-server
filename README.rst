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


Virtual environment
===================

To create a working virtual environment::

    virtualenv venv
    . venv/bin/activate
    poetry install
    nodeenv venv/node -n 17.1.0
    . venv/node/bin/activate
    npm install -g
    npm install -g serverless

    # Install the Serverless plugin `serverless-azure-functions`.
    # https://www.serverless.com/framework/docs/guides/plugins#installing-plugins
    npm install serverless-azure-functions


Running offline
===============

To run offline for testing purposes, once you have a virtual environment::

    . venv/bin/activate
    . venv/node/bin/activate
    serverless offline


To expose the offline server running on port 7071 to the Web,
you can use PageKite::


    pagekite 7071 yourname.pagekite.me


This lets you test the GitHub hooks while easily iterating.

Deployment
==========

To deploy to Azure Functions::

    serverless deploy


Refer to [Serverless Azure docs](https://serverless.com/framework/docs/providers/azure/guide/intro/) for more information.

To inspect a package before deploying
(such as for checking whether large useless files are included),
build a package and inspect it before deploying::

    serverless package

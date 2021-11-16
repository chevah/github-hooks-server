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


Development
============

To create a working environment:

```sh
virtualenv venv
. venv/bin/activate
poetry install
nodeenv venv/node
. venv/node/bin/activate
npm install -g

# Install the Serverless plugin `serverless-azure-functions`.
# https://www.serverless.com/framework/docs/guides/plugins#installing-plugins
serverless plugin install -n serverless-azure-functions
```


Running offline
===============

To run offline for testing purposes:

```sh
. venv/bin/activate
. venv/node/bin/activate
serverless offline
```

Deployment
==========

To deploy to Azure Functions:

```sh
sls deploy
```

Refer to [Serverless Azure docs](https://serverless.com/framework/docs/providers/azure/guide/intro/) for more information.

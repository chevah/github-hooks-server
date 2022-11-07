github-hooks-server
===================

Custom handling of GitHub pull requests.

It manages the labels for a PR to keep track of the review state for a PR:

* needs-review
* needs-changes
* needs-merge

The GitHub Token needs to have triage permissions to the managed repo,
and the account must be a member of the organization to be able to see teams.

The code is public but the package is private.
It is not / and should not be published on PyPi.

Also tests are designed to run from Chevah VPN with access to staging Trac
instance.


Virtual environment
===================

To create a working virtual environment::

    virtualenv -p 3.8 venv  # Last Python version supported by serverless-azure-functions
    . venv/bin/activate
    pip install poetry
    poetry install
    nodeenv venv/node -n 17.1.0
    . venv/node/bin/activate
    npm install -g
    npm install -g serverless

    # Install the Serverless plugin `serverless-azure-functions`.
    # https://www.serverless.com/framework/docs/guides/plugins#installing-plugins
    npm install serverless-azure-functions


To activate the virtual environment::

    . venv/bin/activate
    . venv/node/bin/activate


Running offline
===============

To run offline for testing purposes, once you have a virtual environment::

    . venv/bin/activate
    . venv/node/bin/activate
    serverless offline


Now you can send a POST request to the `hook` function, or a GET request to the `ping` function:

    http://localhost:7071/api/ping

To expose the offline server running on port 7071 to the Web,
you can use PageKite::


    pagekite 7071 yourname.pagekite.me


This lets you test the
`GitHub hooks <https://github.com/chevah/github-hooks-server/settings/hooks>`_
while easily iterating.

Deployment
==========

Make sure `config.ini` has an appropriate `github-token` value.

We can not deploy using Serverless on Azure Functions anymore.
The upload of the package succeeds, but updating the Function App does not.

Therefore, we have to deploy using Azure CLI and Azure Functions Core Tools.
Serverless is still used, because it generates the proper package.

Install
`Azure CLI <https://github.com/Azure/azure-cli>`_ and
`Azure Functions Core Tools
<https://github.com/Azure/azure-functions-core-tools>`_.

Also install `pip_tools` (via `pip`) for `pip-compile`,
to generate hashes for `requirements.txt`, as a workaround to
a `poetry issue <https://github.com/python-poetry/poetry/issues/2060#issuecomment-623737835>`_.

Then, in the virtual env::

    poetry export -f requirements.txt --output requirements.txt
    pip-compile --generate-hashes -o requirements.txt requirements.txt
    # Poetry won't pin setuptools, but Azure wants it to prevent tampering.
    echo 'setuptools==59.6.0 --hash=sha256:4ce92f1e1f8f01233ee9952c04f6b81d1e02939d6e1b488428154974a4d0783e' >> requirements.txt
    serverless package
    cd .serverless/
    unzip githubhooks.zip
    az login
    func azure functionapp publish sls-weur-dev-githubhooks --python

`Courtesy of this comment
<https://github.com/serverless/serverless-azure-functions/issues/505#issuecomment-713218520>`_.

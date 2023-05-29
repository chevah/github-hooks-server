github-hooks-server
===================

Custom handling of GitHub pull requests.

It manages the labels for a PR to keep track of the review state for a PR:

* needs-review
* needs-changes
* needs-merge

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


To activate a virtual environment that already exists::

    . venv/bin/activate
    . venv/node/bin/activate


Deployment
==========

Make sure `config-secrets.ini` has an appropriate `github-token` value::

    [github_hooks_server]
    github-token = abc123

The GitHub token needs to have triage permission for the managed repo,
and the account must be a member of the organization to be able to see teams.

Install
`Azure CLI <https://github.com/Azure/azure-cli>`_ and
`Azure Functions Core Tools
<https://github.com/Azure/azure-functions-core-tools>`_.

Also install `pip_tools` (via `pip`) for `pip-compile`,
to generate hashes for `requirements.txt`, as a workaround to
a `poetry issue <https://github.com/python-poetry/poetry/issues/2060#issuecomment-623737835>`_.

Then, in the virtual env::

    poetry export -f requirements.txt --output requirements.txt
    pip-compile --generate-hashes -o requirements.txt.new requirements.txt
    mv requirements.txt.new requirements.txt
    # Poetry won't pin setuptools, but Azure wants it to prevent tampering.
    echo 'setuptools==59.6.0 --hash=sha256:4ce92f1e1f8f01233ee9952c04f6b81d1e02939d6e1b488428154974a4d0783e' >> requirements.txt
    # Before running build-package, make sure all needed files are provided.
    ./build-package.sh
    cd build/
    az login
    func azure functionapp publish sls-weur-dev-githubhooks --python

`Courtesy of this comment
<https://github.com/serverless/serverless-azure-functions/issues/505#issuecomment-713218520>`_.

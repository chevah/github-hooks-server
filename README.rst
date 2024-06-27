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

    virtualenv -p 3.11 venv
    . venv/bin/activate
    pip install poetry poetry-plugin-export
    poetry install


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

On Arch Linux, these packages are on the AUR named `azure-cli-bin` and `azure-functions-core-tools-bin`. The `azure-cli` package from the official Arch repository did **NOT** work.

Then, in the virtual env::

    poetry lock  # Uses pyproject.toml to create/update poetry.lock
    poetry export -f requirements.txt --output requirements.txt
    # Poetry won't pin setuptools, but Azure wants it to prevent tampering.
    echo 'setuptools==70.1.0 --hash=sha256:d9b8b771455a97c8a9f3ab3448ebe0b29b5e105f1228bba41028be116985a267' >> requirements.txt
    # Before running build-package, make sure all needed files are provided.
    ./build-package.sh
    cd build/
    az login
    func azure functionapp publish sls-weur-dev-githubhooks --python

`Courtesy of this comment
<https://github.com/serverless/serverless-azure-functions/issues/505#issuecomment-713218520>`_.


Updating dependencies
=====================

The `poetry install` step above uses the `poetry.lock` file.
To update dependencies, remove `poetry.lock`, remove the `venv` directory, then execute the steps above again.

For `setuptools`, manually check the SHA256 of the last release on PyPI.
For example, in the case of version 70.1.0: https://pypi.org/project/setuptools/70.1.0/#copy-hash-modal-f2f344e1-1f13-4149-9ceb-38b979703ec7


Running tests
-------------

To run the Handler tests (warning: we have tests connecting to GitHub)::

    # Run all tests
    pytest chevah/github_hooks_server/tests/test_handler.py

    # Run a specific test
    pytest chevah/github_hooks_server/tests/test_handler.py::TestHandler::test_shouldHandlePull

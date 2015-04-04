github-hooks-server
===================

Custom handling of GitHub hooks for Chevah Project.

It keeps Trac and GitHub in sync based on Chevah's own workflow.

To launch the server you will need to store the Trac credentials:ip in a file.
See `scripts/start-chevah-github-hooks.py` for usage.

The code is public but the package is private. It is not / and should not
be published on PyPi.
Also tests are designed to run from Chevah VPN with access to staging Trac
instance.


Development
-----------

If starting with a clean repo, install virtualenv and dev requirements::

    make deps

Virtual environment is created in `build/` folder.::

    . build/bin/activate

Run tests::
    make test
    or
    nosetests

Check the server launch, but you can not do to many things as it needs to be
fed with GitHub hooks and to connect to a Trac instance::
    make run

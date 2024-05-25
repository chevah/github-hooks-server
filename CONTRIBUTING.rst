!!! This file is obsolete. See README.rst

Development
-----------

To launch the server you will need to store the secrets in a file.
See `scripts/start-chevah-github-hooks.py` for usage.

The passwords to Trac and GitHub are protected using git-secret.

If starting with a clean repo, install virtualenv and dev requirements::

    make deps

Virtual environment is created in `build/` folder.::

    . build/bin/activate

Run tests::
    make test
    or
    nosetests


Manual starting
--------------

You can manually launch it on your dev system.
In this env it can't do many things as it needs access to Trac instance and
buildbot instance.

You will need a trac and a buildbot set up.
Start with a config file based on the sample config and then edit it to
match your dev env:

    cp config.ini build/config.ini

To launch the server use:

    make run


Manual hook replay
------------------

In test/ folder update `payload_headers` and `payload_content` files
in which you can put the content based on the content that you find on
GitHub.com.


Trigger the payload push using::

    make payload


Manual hook redirection
-----------------------

In GitHub you can set up the hook for http://PUBLIC.IP:10041/hook/test
and then set up port forwarding::

    ssh -N -T -R 0.0.0.0:8080:localhost:8080 user@PUBLIC.IP

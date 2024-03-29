from setuptools import Command, find_packages, setup
import os

VERSION = '1.0.0'


class PublishCommand(Command):
    """
    Publish the source distribution to private Chevah PyPi server.
    """

    description = "copy distributable to Chevah cache folder"
    user_options = []

    def initialize_options(self):
        self.cwd = None

    def finalize_options(self):
        self.cwd = os.getcwd()

    def run(self):
        assert os.getcwd() == self.cwd, (
            'Must be in package root: %s' % self.cwd)
        self.run_command('bdist_wheel')
        # Upload package to Chevah PyPi server.
        upload_command = self.distribution.get_command_obj('upload')
        upload_command.repository = u'chevah'
        self.run_command('upload')


distribution = setup(
    name="chevah-github-hooks-server",
    version=VERSION,
    maintainer='Adi Roiban',
    maintainer_email='adi.roiban@chevah.com',
    license='MIT',
    platforms='any',
    description="Custom handling of GitHub Hooks for Chevah Project.",
    long_description="",
    url='http://www.chevah.com',
    namespace_packages=['chevah'],
    packages=find_packages('.'),
    package_data={
        'chevah.github_hooks_server': ['author-aliases.txt'],
        },
    install_requires=[
        'github3.py==3.0.0',
        'azure-functions==1.7.2',
        'azure-functions-worker==1.1.9',
        ],
    extras_require={
        'dev': [
            'mock',
            'nose',
            'pyflakes',
            'pep8',
            'nodeenv==1.6.0',
            ],
    },
    cmdclass={
        'publish': PublishCommand,
        },
    )

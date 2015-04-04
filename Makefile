all: test
	

env:
	@if [ ! -d "build" ]; then virtualenv build; fi


deps: env
	@build/bin/pip install -Ue '.[dev]'


run:
	# Run against an invalid Trac instance with fake password.
	@echo '127.0.0.1@test:test' > build/trac_test_credentials
	@build/bin/python \
		scripts/start-chevah-github-hooks.py build/trac_test_credentials \
		--nodaemon


lint:
	pyflakes chevah/ scripts/
	pep8 chevah/ scripts/


test: lint
	@build/bin/python setup.py test

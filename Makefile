all: test
	

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi


deps: env
	@build/bin/pip install -Ue '.[dev]' \
		--index-url http://pypi.chevah.com/simple \
		--trusted-host pypi.chevah.com


run:
	@build/bin/python \
		scripts/start-chevah-github-hooks.py \
		test/config.ini \
		--port tcp:8080 \
		--nodaemon


HEADERS := $(shell while read line; do echo -n "-H '$$line' "; done < test/payload_headers)

payload:
	curl -v $(HEADERS) -d @test/payload_content localhost:8080/buildmaster


lint:
	@build/bin/pyflakes chevah/ scripts/
	@build/bin/pep8 chevah/ scripts/


test:
	@build/bin/nosetests chevah.github_hooks_server.tests -v --with-id

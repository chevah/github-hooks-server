all: test
	

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi


deps: env
	@build/bin/pip install -Ue '.[dev]' \
		--index-url http://deag.chevah.com:10042 \
		--trusted-host deag.chevah.com


run:
	@build/bin/python \
		scripts/start-chevah-github-hooks.py \
		build/test_credentials \
		--port tcp:10041 \
		--nodaemon


HEADERS := $(shell while read line; do echo -n "-H '$$line' "; done < build/payload_headers)

payload:
	curl -v $(HEADERS) -d @build/payload_content localhost:8080/buildmaster


lint:
	@build/bin/pyflakes chevah/ scripts/
	@build/bin/pep8 chevah/ scripts/


test:
	@build/bin/nosetests chevah.github_hooks_server.tests -v --with-id

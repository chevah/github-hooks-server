all: test
	

clean:
	rm -rf build

env:
	@if [ ! -d "build" ]; then virtualenv build; fi


deps: env
	@build/bin/pip install -Ue '.[dev]'


run:
	@build/bin/python \
		scripts/start-chevah-github-hooks.py \
		build/test_credentials \
		--nodaemon


HEADERS := $(shell while read line; do echo -n "-H '$$line' "; done < build/payload_headers)

payload:
	curl -v $(HEADERS) -d @build/payload_content localhost:8080/buildmaster


lint:
	@build/bin/pyflakes chevah/ scripts/
	@build/bin/pep8 chevah/ scripts/


test: lint
	@build/bin/python setup.py test

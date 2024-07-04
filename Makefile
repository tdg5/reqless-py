all: test

.PHONY: clean
clean:
	# Remove the build
	rm -rf build dist
	# And all of our pyc files
	find . -name '*.pyc' -delete
	# And lastly, .coverage files
	find . -name .coverage -delete

.PHONY: reqless-core
reqless-core:
	# Ensure reqless-core is built
	make -C reqless/reqless-core/
	cp reqless/reqless-core/reqless.lua reqless/lua/
	cp reqless/reqless-core/reqless-lib.lua reqless/lua/

.PHONY: test-with-coverage
test-with-coverage: reqless-core
	coverage run -m pytest
	coverage report | tee .meta/coverage/report.txt
	coverage-badge -f -o .meta/coverage/badge.svg

requirements:
	pip freeze | grep -v -e reqless > requirements.txt

.PHONY: test
test:
	pytest

# style the code according to accepted standards for the repo
.PHONY: style
style:
	pre-commit run --all-files -c .pre-commit-config.yaml

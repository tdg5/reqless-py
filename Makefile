all: test

.PHONY: clean
clean:
	# Remove the build
	rm -rf build dist
	# And all of our pyc files
	find . -name '*.pyc' -delete
	# And lastly, .coverage files
	find . -name .coverage -delete

.PHONY: qless-core
qless-core:
	# Ensure qless-core is built
	make -C reqless/qless-core/
	cp reqless/qless-core/qless.lua reqless/lua/
	cp reqless/qless-core/qless-lib.lua reqless/lua/

.PHONY: test-with-coverage
test-with-coverage: qless-core
	coverage run -m pytest

requirements:
	pip freeze | grep -v -e reqless > requirements.txt

.PHONY: test
test:
	pytest

# style the code according to accepted standards for the repo
.PHONY: style
style:
	pre-commit run --all-files -c .pre-commit-config.yaml

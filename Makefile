.PHONY: help
# show this help
help:
	@# prints help for rules preceded with comment
	@# https://stackoverflow.com/a/35730928
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' Makefile | column -s: -t

.PHONY: fe
# install/build frontend
fe: fe-install fe-build lsp

.PHONY: lsp
# install/build lsp
lsp: lsp-install lsp-build

.PHONY: py
# editable python install; only need to run once
py:
	pip install -e .[dev]

.PHONY: check
# run all checks
check: fe-check py-check

.PHONY: check-test
# run all checks and tests
check-test: check fe-test e2e py-test

.PHONY: test
# run all checks and tests
test: fe-test e2e py-test

.PHONY: fe-check
# check frontend
fe-check: fe-lint fe-typecheck

.PHONY: fe-test
# test frontend
fe-test:
	cd frontend; CI=true pnpm test

.PHONY: e2e
# test end-to-end
e2e:
	cd frontend; npx playwright install; npx playwright test

.PHONY: fe-lint
fe-lint:
	cd frontend; pnpm lint:fix

.PHONY: fe-typecheck
fe-typecheck:
	cd frontend; pnpm typecheck

.PHONY: py-check
# check python
py-check:
	./scripts/pyfix.sh

.PHONY: py-test
# test python
py-test:
	pytest

.PHONY: fe-build
fe-build:
	./scripts/buildfrontend.sh

.PHONY: fe-install
fe-install:
	cd frontend; pnpm install

.PHONY: lsp-build
lsp-build:
	./scripts/buildlsp.sh

.PHONY: lsp-install
lsp-install:
	cd lsp; pnpm install

.PHONY: install-all
# install everything; takes a long time due to editable install
install-all: fe py

.PHONY: wheel
# build wheel
wheel:
	python -m build

.PHONY: storybook
storybook:
	cd frontend; pnpm storybook

.PHONY: docs
# build docs
# use make ARGS="-a" docs to force docs to rebuild, useful when
# modifying static files / assets
docs:
	sphinx-build $(ARGS) docs/ docs/_build

.PHONY: docs-auto
# autobuild docs
docs-auto:
	sphinx-autobuild $(ARGS) docs/ docs/_build

.PHONY: docs-clean
# remove built docs
docs-clean:
	cd docs && make clean

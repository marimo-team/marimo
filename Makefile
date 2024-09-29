.PHONY: help
# show this help
help:
	@# prints help for rules preceded with comment
	@# https://stackoverflow.com/a/35730928
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' Makefile | column -s: -t

.PHONY: required-build-tools
expect-tools:
	@if ! /usr/bin/which -s pnpm typos pytest2; then \
		echo "📦 pnpm, pytest, typos-cli required to build and test."; \
		if ! /usr/bin/which -s pnpm; then \
		    echo "💡 Please perform 'npm install -g pnpm@8' or use your preferred package manager."; \
        fi; \
		if ! /usr/bin/which -s pytest; then \
		    echo "💡 Please perform 'pip install -e .[dev]' to add pytest and other dev requirements."; \
        fi; \
		if ! /usr/bin/which -s typos; then \
		  echo "💡 Please perform 'brew install typos-cli', 'cargo install typos-cli' or use your preferred package manager."; \
	    fi; \
	fi

# package frontend into marimo/
.PHONY: fe
fe: expect-tools marimo/_static marimo/_lsp

# install/build frontend if anything under frontend/src or (top-level)
# frontend/ has changed
marimo/_static: $(shell find frontend/src) $(wildcard frontend/*)
	cd frontend; pnpm install; cd ..; ./scripts/buildfrontend.sh

# install/build lsp if anything in lsp/ has changed
marimo/_lsp: $(shell find lsp)
	cd lsp; pnpm install; cd ..; ./scripts/buildlsp.sh

.PHONY: py
# editable python install; only need to run once
py:
	pip install -e .[dev]

.PHONY: check
# run all checks
check: fe-check py-check

.PHONY: check-test
# run all checks and tests
check-test: check fe-test py-test e2e

.PHONY: test
# run all checks and tests
test: fe-test py-test e2e

.PHONY: fe-check
# check frontend
fe-check: fe-lint fe-typecheck

.PHONY: fe-test
# test frontend
fe-test:
	cd frontend; CI=true pnpm turbo test

.PHONY: e2e
# test end-to-end
e2e:
	cd frontend; npx playwright install; npx playwright test

.PHONY: fe-lint
fe-lint:
	cd frontend/src && typos && cd - && cd frontend && pnpm lint

.PHONY: fe-typecheck
fe-typecheck:
	cd frontend; pnpm turbo typecheck

.PHONY: fe-codegen
fe-codegen:
	cd openapi; pnpm install; pnpm codegen

.PHONY: py-check
# check python
py-check:
	./scripts/pyfix.sh

.PHONY: py-test
# test python
py-test: expect-tools
	cd marimo && typos && cd - && pytest;

.PHONY: py-snapshots
# update html snapshots
py-snapshots:
	pytest tests/_server/templates/test_templates.py
	pytest tests/_server/api/endpoints/test_export.py

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

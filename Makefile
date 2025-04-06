.PHONY: help
# show this help
help:
	@# prints help for rules preceded with comment
	@# https://stackoverflow.com/a/35730928
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' Makefile | column -s: -t

# package frontend into marimo/
.PHONY: fe
fe: marimo/_static marimo/_lsp

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
	pip install -e ".[dev]"

.PHONY: dev
dev:
	@echo "Starting development servers..."
	@# Start both processes, with marimo in background
	@(trap 'kill %1; exit' INT; \
	marimo edit --no-token --headless /tmp & \
	cd frontend && pnpm dev && cd ..)

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
	cd frontend; pnpm playwright install; pnpm playwright test

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
# typecheck, lint, format python
py-check:
	./scripts/pycheck.sh

.PHONY: py-test
# test python
py-test:
	cd marimo && typos && cd - && hatch run +py=3.12 test-optional:test

.PHONY: py-snapshots
# update snapshots
py-snapshots:
	hatch run +py=3.12 test:test \
		tests/_server/templates/test_templates.py \
		tests/_server/api/endpoints/test_export.py \
		tests/test_api.py

.PHONY: install-all
# install everything; takes a long time due to editable install
install-all: fe py

.PHONY: wheel
# build wheel
wheel:
	hatch build

.PHONY: storybook
storybook:
	cd frontend; pnpm storybook

.PHONY: docs
# build docs
# use make ARGS="-a" docs to force docs to rebuild, useful when
# modifying static files / assets
docs:
	hatch run docs:build $(ARGS)

.PHONY: docs-serve
docs-serve:
	hatch run docs:serve $(ARGS)

.PHONY: docs-clean
# remove built docs
docs-clean:
	hatch run docs:clean

# Makefile for marimo - Development and build tasks
# Prerequisites:
#   - hatch: for environment permutations management and testing
#   - uv: for Python dependency management
#   - pnpm: for frontend development
#   - Node.js: for frontend development

.PHONY: help
# 📖 Show available commands
help:
	@printf "\nMarimo Development Commands:\n\n"
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_-]+:/{printf "  \033[36m%-20s\033[0m %s\n", substr($$1,1,index($$1,":")-1),c}1{c=0}' $(MAKEFILE_LIST)
	@printf "\nRun 'make check-prereqs' and 'make install-all' to get started!\n\n"

###############
# Setup Tasks #
###############

.PHONY: install-all
# 🚀 First-time setup: Install all dependencies (frontend & Python)
install-all: fe py

.PHONY: check-prereqs
# ✓ Check if all required tools are installed
check-prereqs:
	@command -v pnpm >/dev/null 2>&1 || { echo "pnpm is required. See https://pnpm.io/installation"; exit 1; }
	@pnpm -v | grep -vq "^[0-8]\." || { echo "pnpm v9+ is required. Current version: $(shell pnpm -v)"; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "uv is required. See https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	@command -v hatch >/dev/null 2>&1 || { echo "hatch is required. See https://hatch.pypa.io/dev/install/"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "Node.js is required. See https://nodejs.org/en/download/"; exit 1; }
	@node -v | grep -q "v2[0-9]" || { echo "Node.js v20+ is required. Current version: $(shell node -v)"; exit 1; }
	@echo "✅ All prerequisites are installed!"

.PHONY: py
# 🐍 Install Python dependencies in editable mode
py:
	@command -v uv >/dev/null 2>&1 || { echo "uv is required. See https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
	uv pip install --group=dev -e .

######################
# Development Tasks #
######################

.PHONY: fe
# 🔧 Build frontend assets
fe: marimo/_static marimo/_lsp

# 🔧 Install/build frontend if anything under frontend/
marimo/_static: $(shell find frontend/src) $(wildcard frontend/*)
	./scripts/buildfrontend.sh

# 🔧 Install/build lsp if anything in lsp/ has changed
marimo/_lsp: $(shell find packages/lsp)
	./scripts/buildlsp.sh

.PHONY: dev
dev: fe-codegen
	@echo "Starting development servers..."
	@# Start both processes, with marimo in background
	@(trap 'kill %1; exit' INT; \
	uv run marimo edit --no-token --headless /tmp --port 2718 & \
	pnpm dev)
dev-sandbox:
	@echo "Starting development servers..."
	@# Start both processes, with marimo in background
	@(trap 'kill %1; exit' INT; \
	uv run marimo edit /tmp/notebook.py --no-token --headless --sandbox & \
	pnpm dev)

#############
# Testing   #
#############

.PHONY: test
# 🧪 Run all tests (frontend, Python, end-to-end)
test: fe-test py-test e2e

.PHONY: check
# 🧹 Run all checks
check: fe-check py-check

.PHONY: fe-check
# 🧹 Check frontend (lint, typecheck)
fe-check: fe-lint fe-typecheck

.PHONY: fe-test
# 🧪 Test frontend
fe-test:
	CI=true pnpm turbo --filter @marimo-team/frontend test -- --run

.PHONY: e2e
# 🧪 Test end-to-end
e2e:
	cd frontend; pnpm playwright install; pnpm playwright test

.PHONY: fe-lint
# 🧹 Lint frontend
fe-lint:
	cd frontend/src && hatch run typos && cd - && pnpm --filter @marimo-team/frontend lint

.PHONY: fe-typecheck
# 🔍 Typecheck frontend
fe-typecheck:
	pnpm turbo --filter @marimo-team/frontend typecheck

.PHONY: fe-codegen
# 🔄 Generate frontend API
fe-codegen:
	uv run --python=3.12 ./marimo development openapi > packages/openapi/api.yaml
	pnpm run codegen
	pnpm format packages/openapi/

.PHONY: py-check
# 🔍 Typecheck, lint, format python
py-check:
	./scripts/pycheck.sh

.PHONY: typos
# 🔍 Check for typos
typos:
	hatch run typos

.PHONY: py-test
# 🧪 Test python
py-test:
	uvx hatch run typos
	./scripts/pytest.sh --optional $(ARGS)

.PHONY: py-snapshots
# 📸 Update snapshots
py-snapshots:
	hatch run +py=3.12 test:test \
		tests/_server/templates/test_templates.py \
		tests/_server/api/endpoints/test_export.py \
		tests/test_api.py

##############
# Packaging  #
##############

.PHONY: wheel
# 📦 Build wheel
wheel:
	hatch build


#################
# Documentation #
#################

.PHONY: docs
# 📚 Build docs
docs:
	hatch run docs:build

.PHONY: docs-serve
# 📚 Serve docs
docs-serve:
	hatch run docs:serve

.PHONY: storybook
# 🧩 Start Storybook for UI development
storybook:
	pnpm --filter @marimo-team/frontend storybook

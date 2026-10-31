# Contributing Guide

We welcome contributions. _You don't need to be an expert
in frontend or Python development to help out._

## Checklist

Contributions are made through
[pull requests](https://help.github.com/articles/using-pull-requests/).
Before sending a pull request, make sure to do the following:

- [Obtain maintainer approval](#maintainer-approval)
- Lint, typecheck, and format your code
- [Write and run tests](#tests)
- [Provide visual evidence for changes made](#visual-evidence)
- Read and sign the [CLA](https://marimo.io/cla) by commenting on the PR: `I have read the CLA Document and I hereby sign the CLA`

## Maintainer approval

Contributors must obtain maintainer approval before making
pull requests with substantial changes. Substance is not measured only
in lines of code. Here is a non-exhaustive list of changes we consider substantial:

1. changes to the public API;
2. changes to required or optional dependencies;
3. changes to CI workflows;
4. changes with large internal refactors;
5. changes to our documentation architecture;
6. changes to default configuration;
7. opinionated changes to the user interface or user experience;
8. changes to the semantics of marimo's runtime;
9. changes to marimo's file format;
10. changes with many lines of code.

To obtain approval, open a [GitHub
issue](https://github.com/marimo-team/marimo/issues) describing the change you
would like to make and discuss it with a maintainer. If you would like to make
a PR for an issue that already exists, join the conversation in that issue.

**Labels.** We use GitHub [labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels) to categorize issues into two states:

- `needs discussion` — not ready for a PR
- `ready` — ready for a PR

If an issue does not have one of these two labels, assume it is **not ready** for a PR and requires discussion.

### Why is maintainer approval required?

marimo is intentionally designed: we put as much thought into the features we exclude as the ones we include, and a small change can carry a large maintenance cost over time. For examples of that thinking, see our [MEPs repo](https://github.com/marimo-team/meps) and [founding essays](https://docs.marimo.io/reading/).

## Setup

_Note: We recommend that Windows developers use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) and clone the marimo repository [into the WSL environment and not the Windows mount](https://learn.microsoft.com/en-us/windows/wsl/filesystems)._

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js](https://nodejs.org/) 22.18+
- [pnpm](https://pnpm.io/installation) 12+

### Getting started

```bash
make fe && make py
make dev
```

This will build the frontend, install Python dependencies in editable mode, and launch the dev server (backend on port 2718, frontend on port 3000).

`make dev` is the day-to-day loop: it serves the frontend from Vite, which is faster to iterate on but not identical to production. Use `pnpm build:watch` when you want a production-like frontend, and `marimo -d edit --no-token` when you want backend debug logs.

### `pre-commit` hooks

You can optionally install [pre-commit](https://pre-commit.com/) hooks to automatically run the validation checks when making a commit:

```bash
uvx pre-commit install
```

## Tests

We have frontend unit tests, Python unit tests, and end-to-end tests.
Code changes should be accompanied by unit tests. Some changes
should also be accompanied by end-to-end tests.

To run all tests:

```bash
make test
```

This can take some time. To run just frontend tests, just Python tests, or just
end-to-end tests, read below.

### Frontend

```bash
make fe-test
```

### Python

```bash
make py-test
```

For a subset, run `uv run --group test pytest <path>`. Use `--group test-optional` when the tests need optional dependencies. Tests use [pytest syntax](https://docs.pytest.org/en/stable/how-to/usage.html).

### End-to-end

Build the frontend first with `make fe` so Playwright runs against your latest changes.

```bash
make e2e
```

From `frontend/`, run `pnpm playwright test --ui` to run interactively, `pnpm playwright test $FILENAME` for one file, or add `--debug` to step through it. See the [Playwright best practices](https://playwright.dev/docs/best-practices).

## Visual evidence

All PRs require visual evidence for user-facing changes. For broad changes, check that other features and components do not regress, including different user flows and edge cases.

For example, if you are adding a new API plugin, ensure the UI shows how different parameters combine together to produce the expected output.

## PRs

When submitting a pull request, marimo will run: lint, typecheck, and test jobs.

We have some labels which can influence which tests are run:

- `test-all`: Run all tests across unchanged files as well.

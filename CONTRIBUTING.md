# Contributing Guide

We welcome contributions. _You don't need to be an expert
in frontend or Python development to help out._

## Checklist

Contributions are made through
[pull requests](https://help.github.com/articles/using-pull-requests/).
Before sending a pull request, make sure to do the following:

- [Obtain maintainer approval](#maintainer-approval)
- [Lint, typecheck, and format](#lint-typecheck-format) your code
- [Write tests](#tests)
- [Run tests](#tests) and check that they pass
- Read the [CLA](https://marimo.io/cla)

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

**Deliberate design.** marimo is an intentionally designed project. We
put just as much thought into the features we exclude as the ones we include, 
in order to provide our users with a simple, consistent, delightful, and
powerful experience.

For examples of the thought we put in, see our [MEPs
repo](https://github.com/marimo-team/meps) and read our [founding
essays](https://docs.marimo.io/reading/).

**Consistency.** Each feature affects the whole product. A change that seems
locally helpful can make the system less consistent and therefore harder to
learn, explain, or evolve.

**Small changes can have large consequences.** Unlike traditional software, in
open source, some changes are irreversible. Even seemingly minor changes — like
adjusting a function signature or adding “just one more option” — can
have long-lasting consequences.

**Maintenance burden.** New features create new work. What may seem like a
small change in lines of code can have a disproportionately large maintenance
cost when integrated over time.

**Review burden.** Though the cost of writing code has decreased, the cost of
reviewing code has not (in fact, it has increased). Asking a maintainer or
community member to review your changes imposes a cost on their time. Building
consensus before making the pull request shows respect.

**Early consensus prevents wasted effort.** Seeking approval before implementing a
substantial change increases the chance that your work will be merged.

## Setup

_Note: We recommend that Windows developers use [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) and clone the marimo repository [into the WSL environment and not the Windows mount](https://learn.microsoft.com/en-us/windows/wsl/filesystems)._

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js](https://nodejs.org/) 22+
- [pnpm](https://pnpm.io/installation) 9+

### Getting started

```bash
make fe && make py
make dev
```

This will build the frontend, install Python dependencies in editable mode, and launch the dev server (backend on port 2718, frontend on port 3000).

> [!TIP]
> On the marimo team we use `uv` + `node`/`pnpm` directly. Alternatively, [pixi](https://github.com/prefix-dev/pixi) can manage the Python and Node toolchains for you (`pixi shell` then proceed as above), and [Gitpod](https://gitpod.io/#https://github.com/marimo-team/marimo) provides a cloud-based dev environment — but we don't officially support either of these and recommend the setup above.

### `pre-commit` hooks

You can optionally install [pre-commit](https://pre-commit.com/) hooks to automatically run the validation checks when making a commit:

```bash
uvx pre-commit install
```

To build the frontend unminified, run:

```bash
NODE_ENV=development make fe -B
```

## `make` commands

> [!NOTE]
> Refer to the [Makefile](Makefile) for the implementation details

| Command        | Category  | Description                                                    |
| -------------- | --------- | -------------------------------------------------------------- |
| `help`         | General   | 📖 Show available commands                                     |
| `install-all`  | Setup     | 🚀 First-time setup: Install all dependencies (frontend & Python) |
| `check-prereqs`| Setup     | ✓ Check if all required tools are installed                    |
| `py`           | Setup     | 🐍 Install Python dependencies in editable mode                |
| `fe`           | Build     | 🔧 Build frontend assets                                       |
| `test`         | Test      | 🧪 Run all tests (frontend, Python, end-to-end)                |
| `check`        | Test      | 🧹 Run all checks                                              |
| `fe-check`     | Lint/Test | 🧹 Check frontend (lint, typecheck)                            |
| `fe-test`      | Test      | 🧪 Test frontend                                               |
| `e2e`          | Test      | 🧪 Test end-to-end                                             |
| `fe-lint`      | Lint      | 🧹 Lint frontend                                               |
| `fe-typecheck` | Lint      | 🔍 Typecheck frontend                                          |
| `fe-codegen`   | Build     | 🔄 Generate frontend API                                       |
| `py-check`     | Lint      | 🔍 Typecheck, lint, format python                              |
| `typos`        | Lint      | 🔍 Check for typos                                             |
| `py-test`      | Test      | 🧪 Test python                                                 |
| `py-snapshots` | Test      | 📸 Update snapshots                                            |
| `wheel`        | Build     | 📦 Build wheel                                                 |
| `docs`         | Docs      | 📚 Build docs                                                  |
| `docs-serve`   | Docs      | 📚 Serve docs                                                  |
| `storybook`    | Docs      | 🧩 Start Storybook for UI development                          |

## Lint, Typecheck, Format

**All checks.**

```bash
make check
```

**Frontend.**

```bash
make fe-check
```

**Python.**

<table>
  <tr>
    <th>Using <code>make</code></th>
    <th>Using <code>uv</code></th>
  </tr>
  <tr>
    <td>
      <pre><code>make py-check         </code></pre>
    </td>
    <td>
      <pre><code>uv run ruff check --fix
uv run ruff format
uv run --only-group typecheck mypy marimo --exclude=marimo/_tutorials/</code></pre>
    </td>
  </tr>
</table>

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

In the root directory, run:

```bash
make fe-test
```

### Python

We use [pytest syntax](https://docs.pytest.org/en/stable/how-to/usage.html) for Python tests.

#### Using Make

```bash
make py-test
```

#### Using uv

Run a specific test

```bash
uv run --python 3.13 --group test pytest tests/_ast/
```

Run all changed tests

```bash
uv run --python 3.13 --group test pytest --picked
```

Run tests with optional dependencies

```bash
uv run --python 3.13 --group test-optional pytest tests/_ast/
```

### End-to-end

We use playwright to write and run end-to-end tests, which exercise both the
marimo library and the frontend.

(The first time you run, you may be prompted by playwright to install some
dependencies; follow those instructions.)

For best practices on writing end-to-end tests, check out the [Best Practices
doc](https://playwright.dev/docs/best-practices).

For frontend tests, you want to build the frontend first with `make fe` so that Playwright works on your latest changes.

**Run end-to-end tests.**

In the root directory, run:

```bash
make e2e
```

**Run tests interactively.**

In `frontend/`:

```bash
pnpm playwright test --ui
```

**Run a specific test.**

In `frontend/`:

<table>
  <tr>
    <th>Without debugger</th>
    <th>With debugger</th>
  </tr>
  <tr>
    <td>
      <pre><code>pnpm playwright test $FILENAME        </code></pre>
    </td>
    <td>
      <pre><code>pnpm playwright test --debug $FILENAME</code></pre>
    </td>
  </tr>
</table>

## Storybook

To open Storybook, run the following:

```bash
cd frontend && pnpm storybook
```

## Hot reloading / development mode

You can develop on marimo with hot reloading on the frontend and/or development
mode on the server (which automatically restarts the server on code changes).
These modes are especially helpful when you're making many small changes and
want to see changes end-to-end very quickly.

For the frontend, you can choose to run slower hot reloading for an environment closer to production.

<table>
  <tr>
    <th>Production</th>
    <th>Development</th>
  </tr>
  <tr>
    <td>
      <pre><code>pnpm build:watch      </code></pre>
    </td>
    <td>
      <pre><code>pnpm dev              </code></pre>
    </td>
  </tr>
</table>

For the backend, we recommend running without auth (`--no-token`):

<table>
  <tr>
    <th>Production</th>
    <th>Debug</th>
  </tr>
  <tr>
    <td>
      <pre><code>marimo edit --no-token   </code></pre>
    </td>
    <td>
      <pre><code>marimo -d edit --no-token</code></pre>
    </td>
  </tr>
</table>

### FAQ

- **When to run with hot-reloading?**: When you are developing on the frontend
  and want to see changes immediately. This is useful for styling, layout, new
  plugins, etc. Developing through the Vite server may have inconsistent
  behavior due to proxied api/websocket request and since the marimo Python
  server is not serving the HTML.
- **When to develop with the frontend in watch mode?**: When you are making few
  frontend changes, or when you want to test the frontend in a way that is
  closer to production.
- **When to run marimo CLI with development mode?**: When you are making
  changes to the backend and want to see debug logs.
  When developing on marimo plugins, you can run with "On module change" as "autorun" to see changes immediately.

**Caveats for running `pnpm dev`**

Running `pnpm dev` will serve the frontend from a Vite dev server, not from the
marimo server. This means that:

1. You will want to run your marimo server with `--headless` and `--no-token` so it does not open a new browser tab, as it will interfere with the frontend dev server.
1. The tradeoff of using the frontend dev server is that it is faster to
   develop on the frontend, but you will not be able to test the frontend in
   the same way that it will be used in production.


## PRs

When submitting a pull request, marimo will run: lint, typecheck, and test jobs.

We have some labels which can influence which tests are run:

- `test-all`: Run all tests across unchanged files as well.

## Your first PR

Marimo has a variety of CI jobs that run on pull requests. All new PRs will fail until you have signed the [CLA](https://marimo.io/cla). Don't fret. You can sign the CLA by leaving a comment in the PR with text of `I have read the CLA Document and I hereby sign the CLA`

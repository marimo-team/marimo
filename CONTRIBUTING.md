# Contributing Guide

We welcome all kinds of contributions. _You don't need to be an expert
in frontend or Python development to help out._

## Checklist

Contributions are made through
[pull requests](https://help.github.com/articles/using-pull-requests/).
Before sending a pull request, make sure to do the following:

- [Lint, typecheck, and format](#lint-typecheck-format) your code
- [Write tests](#tests)
- [Run tests](#tests) and check that they pass
- Read the [CLA](https://marimo.io/cla)

_Please reach out to the marimo team before starting work on a large
contribution._ Get in touch at
[GitHub issues](https://github.com/marimo-team/marimo/issues)
or [on Discord](https://marimo.io/discord?ref=contributing).

## Setup

Install [pixi](https://github.com/prefix-dev/pixi) to manage your development environment. The following command uses `pixi` to launch a development shell with all dependencies installed, using `hatch` as the environment manager.

> [!NOTE]
>
> As an alternative to installing `pixi`, you can try developing in
> [Gitpod](https://gitpod.io/#https://github.com/marimo-team/marimo).
> Note that developing in Gitpod is not officially supported by the marimo team.

```bash
pixi run hatch shell
```

Now you can install the environment frontend and Python dependencies.

```bash
make fe && make py
```

After doing this, you can instantiate your marimo development environment by running the following command.

```bash
make dev
```

You can optionally install [pre-commit](https://pre-commit.com/) hooks to automatically run the validation checks when making a commit:

```bash
uvx pre-commit install
```

To build the frontend unminified, run:

```bash
NODE_OPTIONS=--max_old_space_size=8192 NODE_ENV=development make fe -B
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
    <th>Using <code>hatch</code></th>
  </tr>
  <tr>
    <td>
      <pre><code>make py-check         </code></pre>
    </td>
    <td>
      <pre><code>hatch run lint
hatch run format
hatch run typecheck:check     </code></pre>
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

#### Using Hatch

Run a specific test

```bash
hatch run test:test tests/_ast/
```

Run tests with optional dependencies

```bash
hatch run test-optional:test tests/_ast/
```

Run tests with a specific Python version

```bash
hatch run +py=3.10 test:test tests/_ast/
```

Run all tests across all Python versions

Not recommended since it takes a long time.

```bash
hatch run test:test
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

## Editor settings

If you use vscode, you might find the following `settings.json` useful:

```json
{
  "editor.formatOnSave": true,
  "editor.formatOnPaste": false,
  "[typescript]": {
    "editor.defaultFormatter": "biomejs.biome"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "biomejs.biome"
  }
}
```

## Testing a branch from GitHub

This requires `uv` to be installed. This may take a bit to install frontend dependencies and build the frontend.

```bash
MARIMO_BUILD_FRONTEND=true \
uvx --with git+https://github.com/marimo-team/marimo.git@BRANCH_NAME \
marimo edit
```

Additionally, you can run `marimo` from the main branch:

```bash
MARIMO_BUILD_FRONTEND=true \
uvx --with git+https://github.com/marimo-team/marimo.git \
marimo edit
```

## Release

To release a new version of marimo
1. Edit the version in `marimo/__init__.py`
2. Run `make fe-codegen` to update the OpenAPI specification.
3. Commit the changes and push to GitHub.

## Your first PR

Marimo has a variety of CI jobs that run on pull requests. All new PRs will fail until you have signed the [CLA](https://marimo.io/cla). Don't fret. You can sign the CLA by leaving a comment in the PR with text of `I have read the CLA Document and I hereby sign the CLA`

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

_Please reach out to the marimo team before starting work on a large
contribution._ Get in touch at
[GitHub issues](https://github.com/marimo-team/marimo/issues)
or [on Discord](https://discord.gg/JE7nhX6mD8).

## Prerequisites

To build marimo from source, you'll need to have Node.js, pnpm, GNU make, and
Python (>=3.8) installed.

- Install dev dependencies
  - `pip install -e '.[dev]'`
- Install [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm#using-a-node-version-manager-to-install-nodejs-and-npm) >= 18
  - We use Node.js version 20
- Install [pnpm](https://github.com/pnpm/pnpm) == 8.x
  - `npm install -g pnpm@8`
- Install [typos](https://github.com/crate-ci/typos?tab=readme-ov-file#install)
  - `brew install typos-cli` or `cargo install typos-cli`
- Install [GNU Make](https://www.gnu.org/software/make/) (you may already have it installed)
- Install [Python](https://www.python.org/) >= 3.8. (You may already it installed. To see your version, use `python -V` at the command line.)

And you'll need [pre-commit](https://pre-commit.com/) to run some validation checks:

```bash
pipx install pre-commit  # or `pip install pre-commit` if you have a virtualenv
```

You can optionally install pre-commit hooks to automatically run the validation checks
when making a commit:

```bash
pre-commit install
```

> [!NOTE]
>
> As an alternative to building from source, you can try developing
> [in Gitpod](https://gitpod.io/#https://github.com/marimo-team/marimo).
> Note that developing in Gitpod is not officially supported by the marimo
> team.


## Building from source

Be sure to install the dependencies above before building from source.

### Build from source

After installing the dependencies, run the following in a fresh Python virtual
environment (such as [venv](https://docs.python.org/3/library/venv.html) or
[virtualenv](https://virtualenv.pypa.io/en/latest/)):

```bash
make fe && make py
```

`make fe` builds the frontend. `make py` does an [editable install](https://setuptools.pypa.io/en/latest/userguide/development_mode.html) of marimo.

(All `make` commands should be run in the project's root directory.)

### Building from source, unminified

To build the frontend unminified, run:

```bash
NODE_OPTIONS=--max_old_space_size=8192 NODE_ENV=development make fe -B
```

## `make` commands

| Command        | Category  | Description                                                    |
| -------------- | --------- | -------------------------------------------------------------- |
| `help`         | General   | Show this help                                                 |
| `py`           | Setup     | Editable python install; only need to run once                 |
| `install-all`  | Setup     | Install everything; takes a long time due to editable install  |
| `fe`           | Build     | Package frontend into `marimo/`                                |
| `wheel`        | Build     | Build wheel                                                    |
| `check`        | Test      | Run all checks                                                 |
| `check-test`   | Test      | Run all checks and tests                                       |
| `test`         | Test      | Run all tests                                                  |
| `fe-check`     | Lint/Test | Check frontend                                                 |
| `fe-test`      | Test      | Test frontend                                                  |
| `e2e`          | Test      | Test end-to-end                                                |
| `fe-lint`      | Lint      | Lint frontend                                                  |
| `fe-typecheck` | Lint      | Typecheck frontend                                             |
| `py-check`     | Lint      | Check python                                                   |
| `py-test`      | Test      | Test python                                                    |
| `py-snapshots` | Test      | Update HTML snapshots                                          |
| `storybook`    | Docs      | Run Storybook                                                  |
| `docs`         | Docs      | Build docs. Use `make ARGS="-a" docs` to force docs to rebuild |
| `docs-auto`    | Docs      | Autobuild docs                                                 |
| `docs-clean`   | Docs      | Remove built docs                                              |

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

```bash
make py-check
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

In the root directory, run:

```bash
make fe-test
```

### Python

In the root directory, run

```bash
make py-test
```

### End-to-end

We use playwright to write and run end-to-end tests, which exercise both the
marimo library and the frontend.

(The first time you run, you may be prompted by playwright to install some
dependencies; follow those instructions.)

For best practices on writing end-to-end tests, check out the [Best Practices
doc](https://playwright.dev/docs/best-practices).

**Run end-to-end tests.**

In the root directory, run:

```bash
make e2e
```

**Run tests interactively.**

In `frontend/`:

```bash
npx playwright test --ui
```

**Run a specific test.**

In `frontend/`:

```bash
npx playwright test <filename> --ui
# e.g.
npx playwright test cells.test.ts --ui
```

or

```bash
npx playwright test --debug <filename>
```

## Storybook

To open Storybook, run the following:

```bash
cd frontend/
pnpm storybook
```

## Hot reloading / development mode

You can develop on marimo with hot reloading on the frontend and/or development
mode on the server (which automatically restarts the server on code changes).
These modes especially helpful when you're making many small changes and
want to see changes end-to-end very quickly.

For the frontend, you can run either

```bash
# starts a dev server on localhost:3000 and proxy requests to your marimo server
# has hot reloading and the fastest way to develop the frontend
# read caveats below
pnpm dev
```

### OR

```bash
# OR, in order to test closer to production, you can build the frontend and watch for changes
pnpm build:watch
```

For the backend, we recommend running without auth (`--no-token`):

```bash
marimo edit --no-token
# or in debug mode
marimo -d edit --no-token
```

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

If use use vscode, you might find the following `settings.json` useful:

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

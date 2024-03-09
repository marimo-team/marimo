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

## Building from source

You'll need to build marimo from source to edit and test code.

**Build dependencies.**
To build marimo from source, you'll need to have Node.js, pnpm, GNU make, and
Python (>=3.8) installed.

- Install [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm#using-a-node-version-manager-to-install-nodejs-and-npm)
- Install [pnpm](https://github.com/pnpm/pnpm) with `npm install -g pnpm`
- Install [GNU Make](https://www.gnu.org/software/make/) (you may already have it installed)
- Install [Python](https://www.python.org/). (You may already it installed. To see your version, use
  `python -v` at the command line.)

**Build from source.**
After installing the dependencies, run the following in a fresh Python virtual
environment (such as [venv](https://docs.python.org/3/library/venv.html) or
[virtualenv](https://virtualenv.pypa.io/en/latest/)):

```bash
make fe && make py
```

`make fe` builds the frontend. `make py` does an [editable install](https://setuptools.pypa.io/en/latest/userguide/development_mode.html) of marimo.

(All `make` commands should be run in the project's root directory.)

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

_OR_

```bash
# OR, in order to test closer to production, you can build the frontend and watch for changes
pnpm build:watch
```

For the backend, you can start marimo in development mode with

```bash
marimo -d edit
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
  changes to the backend and you want your changes to be auto-reloaded so you
  don't have to restart the server every time you make a change. If you are
  running the frontend in watch mode, you will want to run the marimo server in
  debug mode so that it will reload on changes.

**Caveats for running `pnpm dev`**

Running `pnpm dev` will serve the frontend from a Vite dev server, not from the
marimo server. This means that:

1. You will want to run your marimo server with `--headless` so it does not open a new browser tab, as it will
   interfere with the frontend dev server.
2. The tradeoff of using the frontend dev server is that it is faster to
   develop on the frontend, but you will not be able to test the frontend in
   the same way that it will be used in production.

## Editor settings

If use use vscode, you might find the following `settings.json` useful:

```json
{
  "editor.formatOnSave": true,
  "editor.formatOnPaste": false,
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "prettier.configPath": "./frontend/.prettierrc.json"
}
```

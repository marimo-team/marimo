# @marimo-team/host

The [marimo host protocol](../../protocols/host/spec.md) lets clients discover
hosts, work with notebooks, and follow their execution. A host manages the
notebooks and Python runtimes; clients interact with it through HTTP operations
and event streams.

`Host.api` defines this contract as an Effect `HttpApi`. Its schemas give host
implementations typed requests, responses, errors, and events, and describe the
same protocol for clients and code generators.

## Installing from GitHub

Select this package's subdirectory at a GitHub revision:

```sh
pnpm add 'github:marimo-team/marimo#<commit>&path:/packages/host'
```

The `prepare` script compiles the checked-in sources into `dist`. pnpm may
require allowing the build for that Git revision in `allowBuilds`.

## Implementing a host

Import `{ Host }` from `@marimo-team/host` and create a handler layer with
`HttpApiBuilder.group(Host.api, "host", ...)`, supplying
an implementation for each operation through `.handle("notebook.create", ...)`.
Effect infers each handler's inputs, result, and allowed errors from the contract.
Your implementation owns storage, runtime execution, idempotency, and event replay.

`Host.layer(Handlers)` assembles the routes and problem-response middleware:

```ts
const Routes = Host.layer(Handlers).pipe(
  Layer.provide(AuthorizationLive),
  Layer.provide(NotebooksLive),
);
```

Provide your services and an implementation of `Host.Authorization`, then serve
`Routes` with an Effect HTTP server or `HttpRouter.toWebHandler`. The
`catalogEvents` and `notebookEvents` helpers encode SSE responses with heartbeats
and cancellation.

For manual composition, use `Layer.provideMerge(Host.problems)` after providing
the handlers to `HttpApiBuilder.layer(Host.api)`. It handles both handler and
router failures, and installs middleware globally on the host's router.

## Generating OpenAPI

Use `toOpenApi()` to export the contract programmatically, or run this command
from the repository root:

```sh
pnpm --silent --dir packages/host openapi > host.openapi.json
```

The exported specification can also generate Python models and event adapters:

```sh
pnpm --dir packages/host codegen:python --output-dir /tmp/host-python
```

Add `--include-experimental` to either command to include document analysis.
Hosts implementing that extension use `AnalysisHost.api` and `AnalysisHost.layer`.

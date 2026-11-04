# @marimo-team/host

The [marimo host protocol](../../protocols/host/spec.md) lets clients discover
hosts, work with notebooks, and follow their execution. A host manages the
notebooks and Python runtimes; clients interact with it through HTTP operations
and event streams.

`Host.api` defines this contract as an Effect `HttpApi`. Its schemas give host
implementations typed requests, responses, errors, and events, and describe the
same protocol for clients and code generators.

## Implementing a host

Import `{ Host }` from `@marimo-team/host` and create a handler layer with
`HttpApiBuilder.group(Host.api, "host", ...)`, supplying
an implementation for each operation through `.handle("notebook.create", ...)`.
Effect infers each handler's inputs, result, and allowed errors from the contract.
Your implementation owns storage, runtime execution, idempotency, and event replay.

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
Hosts implementing that extension use `AnalysisHost.api`.

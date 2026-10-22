# Host protocol

The public contract for discovering local marimo hosts and working with their
notebooks and runtimes.

- [Specification](spec.md)
- [OpenAPI schema](openapi.yaml)
- [JSON and SSE examples](fixtures/)
- [Conformance tests](conformance/README.md)
- [Experimental features](experimental/README.md)

The base OpenAPI schema contains stable contracts. Experimental features live
in `experimental/<feature>/`, with an additive OpenAPI Overlay, specification,
fixtures, and conformance tests.

The composed schema is the source of truth for the Python types in
`marimo/_core/protocol.py`, the typed event adapters in
`marimo/_core/protocol_events.py`, and the TypeScript schemas and types in
`packages/client/src/protocol.ts`. The frontend defines the native
`marimo` extension event itself, with an `unknown` payload.

The editor consumes host events over WebSockets
when its runtime configuration includes a `notebookId`. With
`server.transport = "sse"`, it continues using the legacy `/sse` session
stream, even when a notebook ID is available. The host's SSE endpoint serves
protocol consumers but does not establish the editor session; editor support
requires that session integration as well as host event framing.

Generate and check the Python bindings from the repository root:

```sh
make host-protocol-codegen
make host-protocol-check
uv run --group test pytest tests/_lint/test_host_protocol_overlays.py
```

Generate and check the TypeScript bindings:

```sh
pnpm --dir packages/client codegen
pnpm --dir packages/client codegen:check
pnpm --dir packages/client test
```

Other consumers can generate types from the same schema by pinning a marimo
commit. Use the examples and conformance tests from that commit too.

## Selecting experimental contracts

Both generator scripts default to the stable base. The client package
`codegen` and `codegen:check` commands explicitly include experimental features
for Turbo builds; `codegen:stable` invokes the script without that opt-in.
`--include-experimental` includes
all overlays; `--include-experimental=analysis` selects named features (comma
separated). Unknown names fail. `--check` uses the same selection and compares
against the chosen output directory without writing files.

marimo's checked-in Python bindings and private `@marimo-team/client` include
all experimental features. The Make targets and client package commands opt in
explicitly. To generate stable-only bindings without replacing those files:

```sh
uv run --no-config --locked --script protocols/host/generate.py --output-dir /tmp/host-python
pnpm --dir packages/client codegen:stable --output-dir /tmp/host-typescript
```

`--output-dir` contains `protocol.py` and `protocol_events.py` for Python, or
`protocol.ts` and `operations.ts` for TypeScript. Stable-only generation produces
bindings, not a separate stable build of the handwritten client package; that
package currently consumes experimental Analysis types.

Both language generators use `generate.py` to compose the contract. Its
`--schema` option emits the selected OpenAPI document as JSON for other tools:

```sh
uv run --no-config --locked --script protocols/host/generate.py --schema --include-experimental=analysis > /tmp/host-openapi.json
```

The composer applies Overlay 1.0 `update` actions in feature-name order.
Targets use JSONPath and must match an object or array. Object updates merge
recursively; array targets append an entry. Root updates (`target: $`) can add
paths and components together. Removal actions are not supported.

Generated headers list the selected features, and descriptions identify added
experimental schemas. Compatibility requirements and the process for adding
and graduating features are described in [experimental features](experimental/README.md).

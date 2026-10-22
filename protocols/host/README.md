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

marimo's checked-in Python and TypeScript bindings include all experimental
features. The generation commands above preserve that selection.

To generate stable-only bindings in a separate directory:

```sh
# Python types and event adapters
uv run --no-config --locked --script protocols/host/generate.py --output-dir /tmp/host-python

# TypeScript types, validation schemas, and operation definitions
pnpm --dir packages/client codegen:stable --output-dir /tmp/host-typescript
```

Both generator scripts default to stable-only bindings. Add
`--include-experimental` for all features or
`--include-experimental=analysis` for a specific feature.
Add `--check` to verify existing output without writing files.

Stable-only generation covers the generated bindings; the client package
itself currently requires experimental Analysis types.

See [experimental features](experimental/README.md) for compatibility rules
and instructions for adding features.

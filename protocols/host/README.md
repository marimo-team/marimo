# Host protocol

The public contract for discovering local marimo hosts and working with their
notebooks and runtimes.

- [Specification](spec.md)
- [OpenAPI schema](openapi.yaml)
- [JSON and SSE examples](fixtures/)
- [Conformance tests](conformance/README.md)

The OpenAPI schema is the source of truth for the Python types in
`marimo/_core/protocol.py`, the typed event adapters in
`marimo/_core/protocol_events.py`, and the TypeScript schemas and types in
`packages/client/src/protocol.ts`. The frontend defines the native
`marimo` extension event itself, with an `unknown` payload.

The editor consumes host events through the `/ws` and `/sse` session routes,
which establish the editor session before streaming events. Connection options
such as `session_id`, `types`, and `cursor` are top-level URL parameters.
The host notebook event endpoint also accepts `run_id`; session routes reject
that filter.
Notebook page parameters are forwarded as a URL-encoded query string in the
`query_params` parameter. For example, a notebook's `?types=scatter&tag=a&tag=b`
becomes `query_params=types%3Dscatter%26tag%3Da%26tag%3Db` on the connection URL;
it does not change the stream's `types` filter, and repeated values are preserved.

Missing or empty `query_params` supplies no notebook parameters. Top-level
connection parameters are never exposed as notebook parameters.

Generate and check the Python bindings from the repository root:

```sh
make host-protocol-codegen
make host-protocol-check
```

Generate and check the TypeScript bindings:

```sh
pnpm --dir packages/client codegen
pnpm --dir packages/client codegen:check
pnpm --dir packages/client test
```

Other consumers can generate types from the same schema by pinning a marimo
commit. Use the examples and conformance tests from that commit too.

# Host protocol

The public contract for discovering local marimo hosts and working with their
notebooks and runtimes.

- [Specification](spec.md)
- [OpenAPI schema](openapi.yaml)
- [JSON and SSE examples](fixtures/)
- [Conformance tests](conformance/README.md)

The OpenAPI schema is the source of truth for the Python types in
`marimo/_core/protocol.py` and the frontend schemas and types in
`frontend/src/core/host/protocol.ts`. The frontend generator also adds the
native `marimo` event with an `unknown` payload.

Generate and check the Python bindings from the repository root:

```sh
make host-protocol-codegen
make host-protocol-check
```

Generate and check the frontend bindings:

```sh
pnpm --dir frontend codegen
pnpm --dir frontend codegen:check
pnpm --dir frontend test src/core/host/__tests__/protocol.test.ts
```

Other consumers can generate types from the same schema by pinning a marimo
commit. Use the examples and conformance tests from that commit too.

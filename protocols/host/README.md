# Host protocol

The public contract for discovering local marimo hosts and working with their
notebooks and runtimes.

- [Specification](spec.md)
- [OpenAPI schema](openapi.yaml)
- [JSON and SSE examples](fixtures/)
- [Conformance tests](conformance/README.md)

The OpenAPI schema is the source of truth for `marimo/_core/protocol.py`.
Generate the types and check them from the repository root:

```sh
make host-protocol-codegen
make host-protocol-check
```

Other consumers can generate types from the same schema by pinning a marimo
commit. Use the examples and conformance tests from that commit too.

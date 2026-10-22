# Experimental host protocol features

Experimental features provide a way to develop and validate proposed host APIs
before committing to a stable contract.

Each feature lives in `experimental/<feature>/` with an OpenAPI overlay,
specification, fixtures, and conformance tests. Consumers explicitly
[select the features](../README.md#selecting-experimental-contracts) they support.

- Overlays **MUST NOT** change stable contracts. Review the composed
  specification to verify this.
- Stable clients **MUST** remain correct without opting in.
- Tests **SHOULD** verify feature behavior and compatibility with stable clients.
- Experimental contracts **MAY** change or be removed between releases.

Run `make host-protocol-check` and `pnpm --dir packages/client test --run`
to check generation, fixtures, and stable-client compatibility. Each feature
must also generate a valid contract when selected on its own.

Once implementation experience establishes a stable design, move its contract,
documentation, fixtures, and tests into the core protocol.

## Composing the schema

Both language generators use `generate.py` to compose the contract. To inspect
the OpenAPI schema with selected features as JSON:

```sh
uv run --no-config --locked --script protocols/host/generate.py --schema --include-experimental=analysis > /tmp/host-openapi.json
```

Separate multiple feature names with commas; unknown names fail.
The composer applies Overlay 1.0 `update` actions in feature-name order.
JSONPath targets must match an object or array: object updates merge
recursively, and array updates append an entry. Root updates (`target: $`)
can add paths and components together. Removal actions are not supported.

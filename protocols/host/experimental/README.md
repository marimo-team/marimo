# Experimental host protocol features

Experiments add opt-in contracts without changing the stable protocol.
They may change or be removed between releases, and stable clients keep
working without them.

[Analysis](analysis/spec.md) is the current example. Its
[Effect module](../../../packages/host-protocol/src/experimental/Analysis.ts) appends
an `analysis` row to the object table and builds its own API from that table.
Effect consumers import `@marimo-team/host-protocol/experimental/Analysis`. Other
consumers pass `--experimental` when they
[print the OpenAPI document](../README.md#get-the-openapi-document).

## Add a feature

Keep its Effect definitions under `packages/host-protocol/src/experimental/` and its
specification, fixtures, and conformance tests under
`protocols/host/experimental/<feature>/`. Register the public module in
[`package.json`](../../../packages/host-protocol/package.json) and include its rows
in the document that
[`scripts/openapi.ts`](../../../packages/host-protocol/scripts/openapi.ts) prints
with `--experimental`.

An experiment only adds to the stable protocol. When promoting a feature, move its definitions, documentation, and tests into
the stable protocol.

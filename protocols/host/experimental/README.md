# Experimental host protocol features

Experiments add opt-in contracts to the stable protocol. They may change or
be removed between releases.

```ts
import { Host, Notebook } from "@marimo-team/host-protocol/experimental";
```

`Host.Api` includes every registered feature. `Notebook.StreamEvent` describes
the events on its notebook stream, including `analysis`. Other consumers can
use the same contract by passing `--experimental` when they
[print the OpenAPI document](../README.md#get-the-openapi-document).

## Add a feature

1. Create a module in `packages/host-protocol/src/experimental/`. Import
   `defineFeature` from `./defineFeature.ts` and use
   `export default defineFeature({ ... })`. Supply `objects`
   for new object definitions, `notebookEndpoints` for new Effect HTTP endpoints
   on the Notebook group, or both. Omitted lists default to empty.
   [Analysis.ts](../../../packages/host-protocol/src/experimental/Analysis.ts)
   shows how an object contributes an event to the notebook stream.
2. Register the feature descriptor in
   [features.ts](../../../packages/host-protocol/src/experimental/features.ts).
   For a Widgets feature, the registry entry would be
   `export { default as widgets } from "./Widgets.ts";`. Both the experimental
   entrypoint and OpenAPI use this registry.
3. Put the specification, fixtures, and conformance tests in
   `protocols/host/experimental/<feature>/`. See [Analysis](analysis/spec.md)
   for an example.

When promoting a feature, move its definitions, documentation, and tests into
the stable protocol and remove its experimental registration.

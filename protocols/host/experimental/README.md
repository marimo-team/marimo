# Experimental host protocol features

Experiments add opt-in contracts to the stable protocol. They may change or
be removed between releases.

```ts
import { Schema } from "effect";
import { Host, Notebook, Schemas } from "@marimo-team/host-protocol/experimental";

const decodeDiagnostic = Schema.decodeUnknownSync(Schemas.CellDiagnostic);
type Diagnostic = typeof Schemas.CellDiagnostic.Type;
```

`Host.Api` includes every feature in the experimental entrypoint.
`Notebook.StreamEvent` describes the events on its notebook stream, including
`analysis`. `Schemas` includes the stable schemas and the experimental
`Analysis`, `CellAnalysis`, and `CellDiagnostic` schemas. `Schemas.ObjectKind`
includes the object kinds in this contract. Other consumers can use the same contract by passing `--experimental` when they
[print the OpenAPI document](../README.md#get-the-openapi-document).

## Add a feature

1. Create a module in `packages/host-protocol/src/experimental/features/`. Import
   `defineFeature` from `../defineFeature.ts` and use
   `export default defineFeature({ ... })`. Supply `objects`
   for new object definitions. Under `catalog` or `notebook`, supply `endpoints`
   for HTTP operations and `events` for additional stream event schemas. Each
   object already contributes its event to the streams it declares.
   [analysis.ts](../../../packages/host-protocol/src/experimental/features/analysis.ts)
   shows how an object contributes an event to the notebook stream.
2. Import the feature in the [experimental entrypoint](../../../packages/host-protocol/src/experimental/index.ts)
   and add it to the list passed to `makeHostContract`. For example, a second feature
   named `widgets` would give `makeHostContract([analysis, widgets])`. OpenAPI uses
   the same composed contract.
3. For each schema consumers should be able to name or decode, export the
   schema from the feature module and re-export it
   from [Schemas.ts](../../../packages/host-protocol/src/experimental/Schemas.ts).
4. Put the specification, fixtures, and conformance tests in
   `protocols/host/experimental/<feature>/`. See [Analysis](analysis/spec.md)
   for an example.

When promoting a feature, move its definitions, documentation, and tests into
the stable protocol and remove it from the experimental feature list.

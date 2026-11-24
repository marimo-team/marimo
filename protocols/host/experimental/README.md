# Experimental host protocol features

Use the experimental entrypoint to build a host or client with features such as
[document analysis](analysis/spec.md). These features may change between releases.

```ts
import { Host, Schemas } from "@marimo-team/host-protocol/experimental";
```

Pass `--experimental` to [print the same contract as OpenAPI](../README.md#get-the-openapi-document).

## Add a feature

Create a module in `packages/host-protocol/src/experimental/features/`. If the
module defines a notebook endpoint called `Preview`, its default export can
contribute just that route.

```ts
import { defineFeature } from "../defineFeature.ts";

export default defineFeature({ notebook: { endpoints: [Preview] } });
```

Import the module in the [experimental entrypoint](../../../packages/host-protocol/src/experimental/index.ts)
and pass it alongside the other features in `makeHostContract([analysis, preview])`.
A host that offers the route supplies its handler. Use the catalog group for
host-wide routes.

For a feature that publishes objects, follow [analysis.ts](../../../packages/host-protocol/src/experimental/features/analysis.ts).
The object definition also supplies its stream event. Expose schemas that
consumers need to construct or decode through [Schemas.ts](../../../packages/host-protocol/src/experimental/Schemas.ts).

Keep the spec, fixtures, and conformance tests under
`protocols/host/experimental/<feature>/`, then [regenerate and check the bindings](../README.md#change-a-contract).

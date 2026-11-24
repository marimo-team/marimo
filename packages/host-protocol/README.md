# Host protocol definitions

[`Host.Api`](src/Host.ts) defines the [host protocol](../../protocols/host/spec.md)
with Effect's `HttpApi`. The same definition gives server handler types, an
Effect HTTP client, and the [OpenAPI document](../../protocols/host/README.md#get-the-openapi-document)
that the Python and TypeScript generators read.

[Objects.ts](src/Objects.ts) lists the objects a host publishes and the streams
that carry them. To include all experimental objects and notebook endpoints,
use the experimental entrypoint in the examples below:

```ts
import { Host } from "@marimo-team/host-protocol/experimental";
```

See [experimental features](../../protocols/host/experimental/README.md) for
how to add a feature.

## Implement a host

```ts
import { HttpApiBuilder } from "effect/http-api";
import { Host } from "@marimo-team/host-protocol";

const NotebookRoutes = HttpApiBuilder.group(Host.Api, "Notebook", (handlers) =>
  handlers.handleAll(notebookHandlers),
);
```

Provide `Host.RequestValidation.layer` to the route groups to return an
`invalid-request` problem when a request fails decoding. Also provide a layer
for `Host.HostToken` that checks the host record's token.

## Connect with Effect

```ts
import { Effect } from "effect";
import { HttpApiClient } from "effect/http-api";
import { Host } from "@marimo-team/host-protocol";

const cancel = Effect.gen(function* () {
  const client = yield* HttpApiClient.make(Host.Api, { baseUrl });
  return yield* client.Notebook.cancel({
    params: { notebookId, runId },
    headers: { idempotencyKey },
  });
});
```

For a client without Effect, use [`@marimo-team/client`](../client/README.md).

## Working on the package

```sh
pnpm --dir packages/host-protocol typecheck
pnpm --dir packages/host-protocol test
pnpm --dir packages/host-protocol lint
pnpm --dir packages/host-protocol build
```

After a change to the definitions,
[regenerate and check all outputs](../../protocols/host/README.md#change-a-contract).

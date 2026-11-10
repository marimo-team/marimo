# Host protocol definitions

[`Host.Api`](src/Host.ts) defines the [host protocol](../../protocols/host/spec.md)
with Effect's `HttpApi`. The same definition gives server handler types, an
Effect HTTP client, and the [OpenAPI document](../../protocols/host/README.md#get-the-openapi-document)
that the Python and TypeScript generators read.

Start with [`Objects.ts`](src/Objects.ts), the table of objects a host
publishes. The events come from that table, and an
[experimental feature](../../protocols/host/experimental/README.md) appends
rows to it.

## Implement a host

```ts
import { HttpApiBuilder } from "effect/http-api";
import { Host } from "@marimo-team/host-protocol";

const NotebookRoutes = HttpApiBuilder.group(Host.Api, "Notebook", (handlers) =>
  handlers.handleAll(notebookHandlers),
);
```

A host also provides a layer for `Host.HostToken`, which admits requests that
carry the host record's token.

## Connect with Effect

```ts
const client = yield* HttpApiClient.make(Host.Api, { baseUrl });
yield* client.Notebook.cancel({
  params: { notebookId, runId },
  headers: { idempotencyKey },
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

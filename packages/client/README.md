# @marimo-team/client

Connect to a marimo host to find notebooks, read their state, and request
edits or execution. A host serves notebooks through the
[host protocol](../../protocols/host/spec.md). `Client` works with the host's
catalog. `NotebookClient` works with one notebook.

## Connect to a host

Give `Client` the host's API base URL and token. These can come from your
application's configuration or the host's
[local discovery record](../../protocols/host/spec.md#local-discovery).

```ts
import { Client } from "@marimo-team/client";

const client = new Client("http://127.0.0.1:2718/api/marimo/v1", {
  token: "your-token",
});
```

Requests use HTTP and event streams use server-sent events. Pass `fetch` or
`headers` alongside `token` to customize requests.

## Find notebooks

The catalog stream describes the host's notebooks, projects, runtimes, and
attachments. It also reports the host's capabilities. This example prints
the notebooks the host currently knows about.

```ts
for await (const event of client.events({ types: ["notebook"] })) {
  if (event.event === "notebook") {
    console.log(event.data.notebook.id, event.data.notebook.name);
  }
  if (event.event === "ready") break;
}
```

`ready` ends the initial snapshot. Breaking out closes the stream. Projects
may still be indexing when `ready` arrives, so more notebooks can appear
afterward.

## Work with a notebook

Use an id or a notebook record from the catalog to get a `NotebookClient`.
This example reads the document, prints its cell count, and asks the host
to save it. It assumes the notebook supports `notebook.save`.

```ts
import type { DocumentOutput } from "@marimo-team/client/protocol";

const notebook = client.notebook("n1");
let document: DocumentOutput | undefined;

for await (const event of notebook.events({ types: ["document"] })) {
  if (event.event === "document") document = event.data.document;
  if (event.event === "reset") document = undefined;
  if (event.event === "ready") break;
}

if (document === undefined) throw new Error("The host did not send a document");
console.log(`${document.order.length} cells`);

const result = await notebook.save({ ifMatch: document.etag });
if (result.ok) {
  console.log("Saved", result.data.document.etag);
} else {
  console.error(result.problem);
}
```

`ifMatch` makes the document's etag a precondition. If the document changes
before the save, the host returns a conflict problem. Other actions, such
as `edit` and `run`, use the same result shape. The notebook's advertised
operations describe which actions it permits. Invalid request data,
invalid responses, and connection failures throw.

You can also construct a `NotebookClient` directly when you already know
the notebook's URL.

## Follow changes

Keep iterating after `ready` to follow changes. Streams reconnect and resume
from their last cursor. If they cannot resume, they deliver `reset` followed
by a new snapshot. Discard accumulated state on `reset` before applying the
snapshot.

To maintain a notebook list or document state from events, see the
[reducer guide](REDUCERS.md).

To follow events over a WebSocket or another connection, see the
[custom transport guide](TRANSPORTS.md).

## Contributing

The [host protocol](../../protocols/host/spec.md) explains the model and
behavior. [OpenAPI](../../protocols/host/openapi.yaml) defines the routes and
payloads. `@marimo-team/client/protocol` exports the TypeScript types and Zod
schemas generated from it.

Run these commands from the repository root. See
[CONTRIBUTING.md](../../CONTRIBUTING.md) for setup.

The package is consumed from `dist`. Build it once, or watch for changes
while developing.

```sh
pnpm --dir packages/client build
pnpm --dir packages/client build --watch
```

After changing OpenAPI, regenerate the protocol types, schemas, and
operation definitions. `codegen:check` checks that generated files match
the specification.

```sh
pnpm --dir packages/client codegen
pnpm --dir packages/client codegen:check
```

Run the package's tests and typecheck. Omit `--run` to watch tests while
developing.

```sh
pnpm --dir packages/client test --run
pnpm --dir packages/client typecheck
```

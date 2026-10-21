# @marimo-team/client

A typed client for notebooks served by a marimo host. Hosts expose each
notebook through the [host protocol](../../protocols/host/README.md), an HTTP
API with its own event stream. `NotebookClient` sends the protocol's requests
for one notebook, addressed by the notebook's URL. Request bodies are
validated before they are sent, and the host's answer comes back as data or a
problem.

`NotebookEvents` follows a notebook's stream. The stream starts with a
snapshot that ends in `ready` and then delivers changes. When a connection
drops, the stream resumes from the last event it received. When it cannot,
it delivers `reset` and a fresh snapshot follows. Given a URL, it follows the
stream over server-sent events, as the protocol defines. Given a
`NotebookTransport`, it follows whatever connection the transport opens.

```ts
import { NotebookClient } from "@marimo-team/client";

const notebook = new NotebookClient(
  "http://127.0.0.1:2718/api/marimo/v1/notebooks/n1",
  { token: "your-token" },
);

const result = await notebook.edit([
  { kind: "delete_cell", id: "c3", base_etag: "*" },
]);
if (!result.ok) {
  console.error(result.problem.type);
}

for await (const event of notebook.events({ types: ["cell", "document"] })) {
  if (event.event === "reset") {
    // Discard what you built. A fresh snapshot follows.
  }
}
```

## Entry points

- `@marimo-team/client` exports `NotebookClient` and `NotebookEvents`.
- `@marimo-team/client/protocol` has the protocol's types and zod 4 schemas,
  generated from `protocols/host/openapi.yaml`. Use the schemas to validate
  protocol data yourself, for example in a host or a conformance test.
- `@marimo-team/client/reducer` composes resources into a pure reducer over a
  notebook stream. It handles `ready`, `reset`, and the notebook's identity,
  so each resource handles the events of its own kinds.

## Development

The package is consumed from `dist`. Build it once, or keep it built while
you work.

```sh
pnpm --dir packages/client build
pnpm --dir packages/client build --watch
```

`src/operations.ts` is generated from the same spec as the schemas. It
describes each operation for the client to call and is not exported.

Regenerate and check the generated files.

```sh
pnpm --dir packages/client codegen
pnpm --dir packages/client codegen:check
```

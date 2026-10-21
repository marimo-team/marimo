# @marimo-team/client

A typed client for the [marimo host protocol](../../protocols/host/README.md).

- `@marimo-team/client/protocol` has the types and zod 4 schemas generated
  from `protocols/host/openapi.yaml`. Clients use the types. Use the schemas
  to validate protocol data yourself, for example in a host or a
  conformance test.
- `@marimo-team/client/reducer` composes resources into a pure reducer over a
  notebook stream. It handles `ready`, `reset`, and the notebook's identity, so
  each resource handles only the events of its own kinds.

The package is consumed from `dist`. Build it once, or keep it built while
you work:

```sh
pnpm --dir packages/client build
pnpm --dir packages/client build --watch
```

`src/operations.ts` is generated from the same spec. It describes each
operation for the client to call and is not exported.

Regenerate and check the generated files:

```sh
pnpm --dir packages/client codegen
pnpm --dir packages/client codegen:check
```

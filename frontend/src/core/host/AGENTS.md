# Host core

Production code may import host modules, `@marimo-team/client`,
`jotai/vanilla`, `zod`, and `@/utils/Logger`. Enforced by
`marimo/host-imports`. Tests are exempt.

The protocol schemas and types live in `@marimo-team/client/protocol`.

Define interfaces here and inject application behavior through adapters.

`notebook-client.ts` follows the notebook with `NotebookEvents` from
`@marimo-team/client`, over a `NotebookTransport` the editor supplies. The
editor's transports for its session routes live in
`core/websocket/transports/notebook.ts`. Each kind of object is a `NotebookResource`
in `resources/` with pure handlers keyed by event name, composed with
`createNotebookReducer`. The client holds one state atom and exposes derived atoms.

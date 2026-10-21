# Host core

Production code may import host modules, `@marimo-team/client`,
`jotai/vanilla`, `zod`, and `@/utils/Logger`. Enforced by
`marimo/host-imports`. Tests are exempt.

The protocol schemas and types live in `@marimo-team/client/protocol`.
The native `marimo` event is a marimo extension and is defined in `events.ts`.

Define interfaces here and inject application behavior through adapters.

`stream.ts` reduces stream events into one state. Each kind of object is a
`Resource` in `resources/` with pure handlers keyed by event name. The stream
handles phase, notebook identity, and control events itself. The client holds
one state atom and exposes derived atoms.

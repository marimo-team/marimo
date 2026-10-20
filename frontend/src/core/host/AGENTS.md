# Host core

Production code may import host modules, `jotai/vanilla`, `zod`, and
`@/utils/Logger`. Enforced by `marimo/host-imports`. Tests are exempt.

Define interfaces here and inject application behavior through adapters.

`stream.ts` reduces stream events into one state. Each kind of object is a
`Resource` in `resources/` with pure handlers keyed by event name. The stream
handles phase, notebook identity, and control events itself. The client holds
one state atom and exposes derived atoms.

# Notebook replica

Production code may import replica modules, `@marimo-team/client`,
`jotai/vanilla`, `zod`, and `@/utils/Logger`. Enforced by
`marimo/replica-imports`. Tests are exempt.

Code outside this directory imports it as `@/core/notebook/replica`.
Enforced by `marimo/module-entry`.

The protocol schemas and types live in `@marimo-team/client/protocol`.
Define interfaces here and inject application behavior through adapters.

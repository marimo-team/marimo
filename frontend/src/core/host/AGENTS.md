# Host core

Keep this module independent of application implementations. Production code
may import other host modules, `jotai/vanilla`, `zod`, and `@/utils/Logger`.
The generated `protocol.ts` may also import the `NotificationMessage` type
from `core/kernel/messages`. This is the only application type exception.
The `marimo/host-imports` lint rule enforces these restrictions, including
type-only imports, re-exports, and dynamic imports. Tests are exempt.

Define required interfaces here and supply implementations from adapters.
The websocket adapter owns transport construction, JSON decoding, and server
close-reason policy. The core validates events and assembles document state.
Native marimo notifications retain their existing type and are forwarded to
`onNotification` without the host envelope.

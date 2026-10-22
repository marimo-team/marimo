# Custom transports

`Client` and `NotebookClient` send HTTP requests and read server-sent events.
To follow events from an existing WebSocket, message channel, or another
source, pass a `Transport` function to `NotebookEvents` or `CatalogEvents`.

The stream calls the transport once for each connection attempt. The
transport receives a cursor and an abort signal. A null cursor requests a
snapshot. Otherwise, the transport sends the cursor to the host to resume
after that position.

Call `open()` when the connection is established. Call `message(event)` for
each decoded protocol event, in order. Close the connection when the signal
is aborted.

Resolve when the connection ends and another attempt makes sense. Reject
when the stream should stop. The stream's `closed` promise rejects with the
same error. Use `StreamStopped` to describe the failure.

The stream validates events, tracks the cursor, delivers events to
subscribers, and reconnects. It delivers `reset` when an interrupted snapshot
must be discarded. The host must also send `reset` when it cannot resume
from the supplied cursor.

The transport sends any filters the host needs. The stream's `types` option
filters delivered events locally. A notebook transport must apply `runId`
itself. Each reconnect must use the same filters.

## Build on server-sent events

`sse` is the transport a stream uses for a URL. Use it directly when a host
serves the protocol's events with a URL that changes between connections or
with frames of its own that end the stream.

```ts
import { NotebookEvents, StreamStopped, sse } from "@marimo-team/client";

const events = new NotebookEvents(
  sse(() => `${base}/events?session_id=${session()}`, {
    token,
    stop: (frame) =>
      frame.event === "close"
        ? new StreamStopped("The session closed")
        : undefined,
  }),
);
```

The URL function runs before each connection. A `StreamStopped` it throws
stops the stream.

See the [transport contract](src/transport/frame.ts) for the function and
event types.

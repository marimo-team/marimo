# Publish custom events

A client calls `notebook.emit` to publish a custom event to readers of a
notebook's stream. The host MUST authorize publication independently of
editing and execution.

```http
POST /notebooks/{notebook_id}/emit
Idempotency-Key: emit-1
Content-Type: application/json

{ "type": "example.message", "data": { "text": "hello" } }
```

The client MUST supply a nonempty `Idempotency-Key` and both body fields.
`type` is a nonempty string in a namespace the producer controls. `data` can
be any JSON value, including `null`. The host MUST treat `data` as opaque.

On success, the host MUST publish one `custom` event on that notebook's
stream. The event's `custom` field carries the submitted `type` and `data`,
and its `request_id` is the request's `Idempotency-Key`. Every reader whose
stream filters include the event can receive it. The
[custom event rules](../../spec.md#custom-events) govern filtering and replay.

The host returns `204 No Content` after publication. It does not wait for a
reader to receive or process the event. If the client repeats the request
with the same key, the [idempotency rules](../../spec.md#requests-and-decisions)
apply. For a recognized retry, the host MUST return `204` without publishing
another event.

[Request example](fixtures/emit-request.json) · [Stream example](../../fixtures/custom-events.sse)

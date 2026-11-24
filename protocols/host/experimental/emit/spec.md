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

For each accepted request, the host MUST publish one
[custom event](../../spec.md#custom-events) on that notebook's stream with
the submitted `type` and `data`. The host treats `data` as opaque and returns
success after publication, even if no reader is connected.

Publication follows the shared [request key and retry rules](../../spec.md#requests-and-decisions).

[Request example](fixtures/emit-request.json) · [Stream example](../../fixtures/custom-events.sse)

# Publish custom events (experimental)

The experimental `notebook.emit` operation publishes a custom event on a
notebook stream.

```http
POST /notebooks/{notebook_id}/emit
Idempotency-Key: emit-1
Content-Type: application/json

{ "type": "example.message", "data": { "text": "hello" } }
```

The request MUST contain a nonempty `type` and a `data` field with any JSON
value, including null. The host MUST NOT interpret the payload.

For each accepted `notebook.emit` request, the host MUST publish exactly one
custom event with the submitted `type` and `data`.
Its `request_id` MUST be the request's `Idempotency-Key`. When a reader's
stream filters include the event, that reader receives it.

The host answers `204 No Content` after publication. This response does not
prove that any client received or processed the event. Under the
[idempotency rules](../../spec.md#requests-and-decisions), an accepted retry
within the retry window MUST NOT publish a second event.

The [custom event rules](../../spec.md#custom-events) define type namespaces,
payload validation, stream filters, replay, and exclusion from snapshots.

Hosts MUST authorize `notebook.emit` independently of editing and execution.
The [Effect feature module](../../../../packages/host-protocol/src/experimental/features/emit.ts)
defines the operation. The [request example](fixtures/emit-request.json) and
[custom event stream example](../../fixtures/custom-events.sse) show its wire format.

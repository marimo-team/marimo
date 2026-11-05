# Experimental UI elements

This experiment publishes edit-mode sliders and tables and provides shared transport for
registered UIElement functions. Other element families are not yet published.

Tables retain their selection as the wire value. Search, paging, summaries,
and export functions use the shared send operation with their existing arguments
and results. Query state remains local to each view; the kernel's existing
search context and selection conversion are unchanged.

A `ui_element` record describes the current wire value and constructor config
of an element owned by `cell_id`. HTML remains the render path. Clients MUST
NOT write config. The kernel remains authoritative for state.

The host retains complete records separately from its replay history. A full
`ui_element` event creates or replaces a record. An `ui_element.update` event
replaces only supplied top-level state keys. Absent keys remain unchanged,
`null` is a value, and top-level deletion is not supported.

Snapshots emit UI elements after attachments and before executions and displays.
Snapshot records omit live cursors and timestamps. Reset clears client records
before a new snapshot. Replay preserves original event metadata.

`ui_element.update` accepts `{state: {value: ...}}` and returns `202` with
`{request_id, id, state}`. An empty partial is also a write. Acceptance does not
change the retained record. The kernel report applies the update and emits
exactly one event per accepted request, including unchanged values. Every
attachment receives it, including the sender. The event can precede the HTTP
response. Retrying an accepted idempotency key does not repeat the write.

The sender MUST create its draft before submission and reconcile by request id.
An acknowledgement for older input MUST NOT replace newer input. A submission
stays bound to the backend that supplied its confirmed state.

The creating cell owns record lifetime. Remove records before rerunning or
deleting that cell, even when another cell displays the element. Runtime stop
removes all records before `runtime.removed`. Removal clears drafts. Object ids
can repeat by construction order, but a replacement starts at its constructor
value. Phase 1 does not restore old state or introduce revisions.

The base authentication, permission, idempotency, and problem rules apply.
Advertise the update capability by permission, independent of runtime state.
Static backends offer no mutation. Invalid request shapes or state keys return
`invalid-request` (400), absent targets return `not-found` (404), and a missing
runtime returns `no-runtime` (409). Rejections emit no acknowledgement.

Both host and client filters map all implemented `ui_element.*` events to
`ui_element`. Stable clients ignore unknown experimental events and preserve
their stream cursor.

## Function calls

`ui_element.send` accepts `{message: {function, args}}`. The function name and
arguments use the existing UIElement function registry. Nonempty `buffers`
are not supported by this handler and return `unsupported-operation` (501).
The send and update capabilities are granted separately.

The caller receives `200` with `{request_id, result}`. `result` preserves the
existing function reply: `{status: {code, title, message}, return_value, found}`.
A null return value is a completed result. Function errors also return this
envelope. Only `found: false` permits the editor to make a new registration
retry. A function that ran MUST NOT be retried with a new key automatically.
This handler always returns a result; fire-and-forget model messages are not
implemented.

Results MUST NOT appear in shared events, replay, or snapshots. The host
correlates each call with a fresh kernel call id. It releases pending calls on
completion, element removal, runtime stop, notebook removal, or timeout.
Removal answers `not-found` (404); after 30 seconds, an outstanding call answers
`tag:marimo.io,2026:host/timeout` (504). Timeout does not cancel kernel work.
Late results are ignored, including results for an element id that was reused.

Within the base retry window, concurrent and later requests with the same key
share the result, including function errors, removal, and timeout. Disconnecting
the HTTP caller does not cancel accepted work. The caller can reconnect and
repeat the key without executing the function again.

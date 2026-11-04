# Experimental UI elements

This experiment covers edit-mode sliders. Other element families
and message operations are outside this implementation.

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

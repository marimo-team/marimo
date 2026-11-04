# Host protocol examples

These files contain protocol messages and stream excerpts. Stream cursors are
opaque. Gaps represent events outside an excerpt or its filter.

## A notebook session

`notebook-events.sse` opens a stream for notebook `n1` during the scratch run
shown in `run.sse`. Its snapshot includes the display and console output
already produced. Both streams end with the same execution and run completion
events, using the same cursors. `cell.json` is cell `c3` from that snapshot,
and `cell-withheld.json`
is the same cell with source withheld from the client: its hashes and version
are unchanged.

`run-cells-request.json` requests `c3`, which defines `x`. In `run-cells.sse`,
the runtime then evaluates `k7f2`, which defines `y` using `x`. The dependent
execution identifies the first execution as its cause and depends on the
revision of `x` it used. Each cell publishes
the variable it bound before it completes, and neither displays a value,
because their code consists of assignments.

`edit.json` edits that document. `edit-response.json` contains the accepted
state, and `edits.sse` shows the cell and document events followed by a save.
Before the save, `edit-conflict-request.json` tries to edit `c3` using its old
etag. `problems/edit-conflict.json` identifies that request's first change as
stale and returns the current cell and document.

`run-failed.sse` and `run-interrupted.sse` show later scratch runs. Each scratch
execution includes its submitted code. Run identities differ from the request
keys carried by their events.

`events.sse` follows the catalog through the client's attachment, the save,
and a runtime stop. Both attachments remain connected after the runtime ends.
`events-reset.sse` shows the resulting catalog after a client's cursor expires.

## Answering input

In a separate session, `inputs.sse` follows a scratch execution that prints,
asks for a name, prints again, and asks for a password. The console and input
items share `seq` ordering, so a client can display them in the order the
execution produced them. The name prompt is answered with this request.

```http
POST /notebooks/n1/runtime/inputs/i1/reply
Idempotency-Key: reply-name
Content-Type: application/json

{ "value": "Trevor" }
```

The request body is in `input-reply-request.json`, and
`input-reply-response.json` contains the `200` response. The response and
answered event contain the prompt's identity, metadata, and updated status.
The event carries the reply's key, `reply-name`, while subsequent execution
events keep the run request's key, `start-input`.

`inputs-reconnect.sse` opens a new stream with
`types=run,execution,console,input` while the password prompt is pending.
Its snapshot includes both prompts, so the client can see that the name was
answered and the password still needs an answer. The live events match
`inputs.sse`, where interruption cancels the password prompt before execution
completes. The final `execution.removed` event removes both inputs.

## Standalone objects

`custom-events.sse` shows a `types=custom` notebook stream: an empty snapshot
ending at `ready`, then a live custom event. `custom-events-replay.sse` resumes
from that `ready` cursor, replaying the same event before the next `ready`.
Its type and payload are illustrative, not a standardized agent-message schema.
If the cursor expires instead, the host sends `reset` and an empty snapshot;
the custom event cannot be recovered from that snapshot.

`execution-restored.json` represents an earlier evaluation of `c3` restored
from storage. Its source is `x = 21`, but its original run and runtime are
unknown. It illustrates a separate restoration scenario, outside the session
above.

The problem responses illustrate individual rejected requests. `record.json` contains fictional local discovery credentials.

Experimental Analysis examples live in [experimental/analysis](../experimental/analysis/spec.md).

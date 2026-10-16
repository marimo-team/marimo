# Host protocol examples

These files contain protocol messages and stream excerpts. Stream cursors are
opaque. Gaps represent events outside an excerpt or its filter.

## A notebook session

`notebook-events.sse` opens a stream for notebook `n1` during the scratch run
shown in `run.sse`. Its snapshot includes the display and console output
already produced. Both streams end with the same execution and run completion
events, using the same cursors. `cell.json` is cell `c3` from that snapshot,
and `analysis.json` is the analysis of that document.

`run-cells-request.json` requests `c3`, which defines `x`. In `run-cells.sse`,
the runtime then evaluates `k7f2`, which defines `y` using `x`. The dependent
execution identifies the first execution as its cause. Each cell publishes
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

`diagnostic.json` illustrates a separate document in which cells `c1` and `c2`
both define `x`. The other problem responses illustrate individual rejected
requests. `record.json` contains fictional local discovery credentials.

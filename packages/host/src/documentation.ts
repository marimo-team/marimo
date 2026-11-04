/* Copyright 2026 Marimo. All rights reserved. */

export const operationDescriptions: Readonly<Record<string, string>> = {
  events: `Sends everything the host has, then every change as it happens.
The response is a stream of server-sent events, so it stays open
and the host appends one event at a time. The catalog is the host
object, its projects, notebooks, runtimes, and attachments.

A new connection starts with one event per object the host knows
about, parents before children, followed by a \`ready\` event.
Snapshot events have no \`id\`; \`ready\` and live events have an \`id\`
line. The most recent \`id\` a client has seen is its position in
the stream. When a connection drops, the client reconnects and
sends that position in the \`Last-Event-ID\` header. If the host
still has the events after that point, it sends them with their
original ids and timestamps, even before the new \`ready\`, and then
\`ready\`. If it does not, or the cursor predates a loss of host
state, it sends \`reset\`, and the client discards what it holds and
receives the full state again. A client also
discards an incomplete snapshot before reconnecting without a
cursor. On \`reset\` it clears its cursor until the next \`ready\`.

\`types\` limits the stream to some kinds of object without changing
ids or positions. It also filters the host object; \`ready\` and
\`reset\` are always sent. Keep the same filter when resuming a
cursor. The host writes a \`: ping\` comment every fifteen seconds
when nothing else is happening. A client that hears nothing for 45
seconds treats the connection as lost and reconnects.
`,
  "notebook.create": `Adds an empty notebook to the project. The request carries the
notebook's own fields, and the host fills in what it owns. In a
project with a \`root\`, \`path\` is required and \`name\` defaults to
the filename; if a file already exists at \`path\`, the host
answers \`conflict\` and leaves it alone. In a project without a
root, \`name\` is required, the host chooses storage, and \`path\` is
null. A request missing the required field is \`invalid-request\`.
The new notebook appears on the catalog stream with this
request's key.
`,
  "notebook.update": `Changes \`path\`, \`name\`, or both. A new \`path\` moves the file
under the same project root, and an attached runtime follows it.
A new \`name\` changes the label shown to people. What the file
contains is content, which this protocol does not write. If a
file already exists at \`path\`, the host answers \`conflict\`.
`,
  "notebook.delete": `Deletes the file. While the notebook has a runtime, the host
answers \`conflict\` instead.
`,
  "notebook.events": `Sends the notebook, its cells and document, its runtime, its
attachments, its runs, their executions, and their items, then
every change as it happens. The
stream follows the same rules as \`/events\`: a snapshot that ends
in \`ready\`, ids as positions, \`Last-Event-ID\` to resume, \`reset\`
when the host cannot, a \`: ping\` comment every fifteen seconds,
and \`types\` to limit the kinds sent. The optional \`run_id\` query
narrows the stream to one run. A cursor belongs to the stream it
came from.

Opening this stream attaches the client to the notebook. An
attachment appears on both streams while the connection is open
and is removed when it closes. Every opening, including a reconnect,
creates a separate attachment. The optional
\`Marimo-Attachment-Identity\` header supplies its \`identity\` so
consumers can group connections from the same client. A shared
identity does not merge attachments or extend their lifetimes.
The snapshot includes every run that is not yet completed, with
its executions and items, plus
any completed results the host retains. Result retention is
independent of replay history. Removed objects are absent from
snapshots; a resumable stream carries their removal events.

The stream may also carry \`custom\` events: namespaced JSON payloads
that describe occurrences rather than object state. These have
cursors and timestamps and appear only in live delivery and replay.
A reset cannot recover custom events whose history
has expired. \`types=custom\` selects them. They do not belong to a
run and are excluded by \`run_id\`.

The opening phase is one consistent cut of the notebook, taken
under the lock that changes to the document take, so reading to
\`ready\` and closing is a snapshot, and \`types=cell,document\` is a
snapshot of the document alone. Cells arrive before the document
that orders them, in the opening phase and after every change, so
each cell named in \`order\` is already available to the client.
The effects of one change to the document arrive
together, with no other event between them.
`,
  "notebook.edit": `Applies an ordered list of changes to the document as one unit.
Each change says what it replaces and carries the etag that state
had when the client read it, so the host can detect competing
edits to that state. Every etag is compared with the document as
it was when the request arrived, so one request can create a cell
and then place it with the order etag the client read. Cells and
the order each have their own etag, so writers can update different
parts independently. An etag of \`*\` skips the check. A \`put_cell\`
with a null etag creates the cell, after or before an existing cell
or at the end; placement has no precondition, so two clients
inserting at once both succeed.

If any precondition is stale, nothing is applied and the host
answers \`conflict\` with \`edit\` naming the first stale change and
carrying the object as it now is. A change that could not apply to
any state, such as an order that leaves out a cell or names one
twice, is \`invalid-request\`.

On success the document has changed, and every attachment sees
the effects on the notebook's stream with this request's key: the
cells that changed, \`cell.removed\` for each deleted cell, and then
the document, with nothing in between. The response carries the new
etags, as of this edit or a later revision, so a client keeps editing without reading again. A
change that changes nothing keeps its etags and sends no events.
Whether the result has reached the store shows in the document's
\`saved_etag\`.
`,
  "notebook.save": `Writes the document as currently applied, after which \`saved_etag\`
equals \`etag\`. The client sends an empty request body because the
host already holds the state. A host that persists every change as
it applies it need not offer this operation. A client shows a save control
when the notebook lists it, and reads whether anything is unsaved
from the two etags either way.

The response is an edit response, because a host may rewrite code
as it saves, for example to format it. Such changes reach the
stream like any other and the response carries the new etags.
\`If-Match\` makes the document etag the client last read a
precondition; the host answers \`conflict\` when the document has
moved on. If the store has changed since the host last read or
wrote it, the host answers \`decision-required\`, offering to
overwrite the store or to reload from it, and the client repeats
the request with its decision and a new key.
`,
  "notebook.open": `Opens the notebook where the host normally shows notebooks, such
as a browser tab or an editor, and returns the URL it used.
Opening may start a runtime. The host omits its token from the URL,
and a client opens it exactly as given. If the notebook
cannot be shown, for example because its file is gone, the host
answers \`conflict\`.
`,
  "runtime.start": `Makes sure the notebook has a running runtime. If it has none, the
host starts one and answers \`202\` with the runtime \`starting\`. The
client then follows \`runtime\` events for that runtime, on either
stream, until its status is \`running\` or \`failed\`. If the notebook
already has a runtime, the host answers \`200\` with it and starts
nothing.

Sometimes the host needs a choice the client did not make, such as
which environment the kernel should run in. It then answers \`409\`
with a problem of type \`decision-required\` that lists the options,
and the client repeats the request with a new \`Idempotency-Key\`
and \`decisions\` filled in. A client that already knows its choice
can include \`decisions\` the first time.
`,
  "runtime.stop": `Ends the runtime for everyone attached to the notebook. A runtime
that is still starting is cancelled; a running kernel is shut
down. Active and queued runs and their unfinished executions complete
with outcome \`interrupted\`. Retained results stay
and are no longer live. The notebook and its attachments stay,
but Python state is lost. The client follows the
runtime on a stream until \`runtime.removed\`. If the notebook has
no runtime, the host answers \`no-runtime\`.
`,
  "runtime.restart": `Stops the runtime and starts a new one with a new id. The stream
shows the old runtime \`terminating\`, then \`runtime.removed\`, then
the new runtime \`starting\`, keeping one runtime attached to the
notebook at a time. Active and queued runs and their unfinished
executions complete with outcome \`interrupted\`. Retained
results stay and are no longer live. The response carries the replacement
runtime in its \`starting\` state. The client follows that id until
it is \`running\` or has \`failed\`. If the notebook has no runtime,
the host answers \`no-runtime\`.
`,
  "runtime.run": `Runs \`code\` in a copy of the notebook runtime's namespace, or runs
\`cells\` of the document. Scratch code stays out of the graph and
its execution carries the submitted code. The runtime's execution
configuration determines whether dependent cells run too. Each cell
gets an execution with its \`cell_id\` and no code.

The host assigns a run id independent of the request's
\`Idempotency-Key\` and answers \`202\` with the run \`queued\` or
\`running\`. The notebook stream carries the executions, their
console and display output, their input requests, and the variables
each cell execution bound. Each execution completes with a \`value\`,
\`error\`, or \`interrupted\` outcome, followed by the run's completion.
Run and execution events carry this request's key. A client that
needs the full stream opens it before sending the request.

A running execution that requests input publishes a pending input
and waits for an answer or cancellation. Any client permitted
\`runtime.input\` may answer through the input's reply route.

A cell in \`cells\` that the document does not have, or whose
\`etag\` is not the one the request carries, is a \`conflict\`
whose \`edit\` names the cell and its index in \`cells\`, and nothing
runs. A client that read the cells from the stream sends their
\`etag\` so that an edit it did not see is a conflict rather
than a run of other code.

Runs execute one at a time in the order the host accepted them.
A run accepted while another is in progress is \`queued\` until the
earlier runs complete. The host answers \`no-runtime\` when the
notebook has no runtime. Within the host's retry window, repeating
the request returns its latest run record without executing again,
even if its outputs have expired.
`,
  "runtime.input": `Accepts an answer for delivery to the identified input and returns
identity, metadata, and updated status \`answered\`. Any client
permitted this operation may answer, regardless of who started
the run. The first accepted reply determines the answer.

The host returns \`conflict\` for a new request to an answered or
cancelled input, or \`not-found\` if the input is unknown, removed,
or belongs to another notebook. Retrying an accepted request with
the same key within the retry window returns the original response,
even after the execution is removed, under the protocol's
idempotency rules.

Hosts offering \`runtime.run\` implement this operation. See
[Answering input](spec.md#answering-input) for delivery semantics.
`,
  "runtime.interrupt": `Stops a run that is in progress. The notebook's stream then
carries its executions with the outcome \`interrupted\` and the
run with status \`completed\` and outcome \`interrupted\` once the
interruption has taken effect. Queued executions end \`interrupted\` and
the running one is interrupted. A run that has not started completes
\`interrupted\` without executing. Once the run is completed, the host
answers \`conflict\`. A host that lists \`runtime.run\` supports this route.
`,
};
export const modelDescriptions: Readonly<Record<string, string>> = {
  ProjectId: `Identifies a project. Unique within the host and unchanged while the project exists.`,
  NotebookId: `Identifies a notebook. Unique within the host and unchanged while the notebook exists.`,
  RuntimeId: `Identifies a runtime. Unique within the host; every start and restart creates a new id.`,
  AttachmentId: `Identifies an attachment. Unique within the host.`,
  RunId: `Identifies a run independently of the request's \`Idempotency-Key\`. Events carry the key in \`request_id\`.`,
  ExecutionId: `Identifies an execution. Unique within the host.`,
  ItemId: `Identifies a console, display, input, or variable item uniquely within the host. Sending an item again with the same id replaces it.`,
  CellId: `Identifies a cell within its notebook. Stable while the host serves the notebook; whether it survives a reload of the store depends on the format. \`setup\` is the setup cell.`,
  HostRecord: `A host record is the file a host writes so that clients can find
it. A host writes \`<marimo-state-dir>/hosts-v1/<id>.json\` once its API
is serving at \`url\`, where \`<id>\` is an identifier the host makes
up each time it starts. The record does not change while the host
runs, and the host removes it when it stops.

A client reads \`version\` before anything else and skips any record
it cannot parse or whose version it does not support. It also
checks that the file and its directory belong to the current user
and cannot be read by others, and that \`url\` points at this
machine.
`,
  Process: `The process that wrote a record. A client checks that a process
with this \`pid\` that started at \`started_at\` still exists. If it
does not, the record is stale and may be removed.
`,
  ObjectType: `The kinds a stream carries, and the values \`types\` accepts. The
catalog stream carries host, project, notebook, runtime, and
attachment. A notebook's stream carries notebook, document,
cell, runtime, attachment, run, execution, console,
display, input, variable, and custom. Custom events describe occurrences
rather than object state.
`,
  Custom: `A notebook occurrence with a producer-defined payload. It is replayed
while event history is retained. Delivery is limited to live events
and replay on the notebook stream, with \`run_id\` omitted from the
stream's filters. The notebook is identified by the stream.
`,
  Host: `What the host can do. There is exactly one host object, and it is
the first object in a snapshot when the filter includes \`host\`.
A resumed stream only sends it if its operations changed since
the cursor. The host sends it again if its operations change.
`,
  ProjectStatus: `How far a host has gotten finding the notebooks in a project.
While it is \`indexing\`, more notebooks are coming. Once it is
\`indexed\`, the host believes it has found every notebook under the
root. A \`partial\` project is one the host stopped scanning on
purpose, or one with something it could not read.
`,
  Project: `A project is a group of notebooks that the host presents together, usually a directory.`,
  Notebook: `A notebook is a document and its results as the host knows them,
usually backed by a file. Its kernel, when it has one, is a
separate object, the runtime. A host sends at most one \`notebook\`
event per second for the same notebook, since \`updated_at\`
changes on every save.
`,
  RuntimeStatus: `Where a runtime is in its life. A \`starting\` runtime is bringing
its kernel up. A \`running\` runtime accepts work. A \`terminating\`
runtime is shutting its kernel down. A \`failed\` runtime could not
start, or its kernel exited unexpectedly. A runtime that has
ended is removed rather than given a status.
`,
  Runtime: `A runtime is a kernel attached to one notebook, and a notebook has
at most one. It ends when a client or the host stops it or its
process exits, and the host then sends \`runtime.removed\`. Every start and restart creates
a new runtime with a new id. Results carry their producer's runtime
id so clients can tell which are live.
`,
  Attachment: `An attachment is a consumer connected to a notebook, such as a
browser tab, an editor, or an agent. Opening the notebook's stream
creates one. It is removed when that connection closes, and not
when the notebook's runtime stops or restarts. Each stream has its
own attachment, even when several share a client identity.
`,
  Lifecycle: `Where a run or execution is in its lifecycle. An execution is
\`queued\` until it starts, \`running\` while code executes, and
\`completed\` once it has ended. How it ended is its \`outcome\`.
`,
  RunOutcome: `How a run ended. \`succeeded\` means its work settled without an
execution error or interruption. \`failed\` means an execution
failed or the host could not finish the cycle. \`interrupted\`
means the cycle was cut short by interruption, even if an earlier
execution failed. Execution outcomes retain their individual results.
`,
  Run: `One bounded cycle of notebook work initiated by an action. It
includes synchronous callbacks and reactive work owned and awaited
by the runtime's scheduler. Context inherited by an independent task
records provenance, not ownership of the cycle. The host completes it
only after all member executions have ended and scheduling for the
cycle has finished. Completion fixes its status and execution membership.
Independently triggered later work starts another run, even when
its cause belongs to an earlier run. Every consumer attached to
the notebook sees it.

Retention is up to the host and independent of replay history.
Hosts SHOULD retain ephemeral results briefly after completion to
allow reconnection. Runs, executions, and items each have removal
events; a cell result may outlive its run.
`,
  DisplayData: `A rendered value.`,
  Variable: `A name a cell's execution bound in the notebook's namespace, with
the revision of its value. The execution binds it as it ends, and
the item is removed with the execution. An update, as when a
state setter runs or a client sets a value, advances the revision
without binding again, and the producer sends the item again with
the same id. Hosts publish a cell execution's variables before its
\`completed\` status, and remove a cell's previous execution and
its items before publishing the next one. A scratch execution's
names live only while it runs, so it publishes no variables.
`,
  Revision: `A variable's value at a point in time. Two revisions are equal
when \`execution\` and \`update\` are equal. Clients compare
revisions for equality.
`,
  Position: `A position within code, using LSP coordinates.`,
  Range: `A span within code.`,
  Related: `A cell involved in an error, possibly the one carrying it.`,
  Error: `A problem shaped like an LSP diagnostic. Further members are
kind-specific, as in Problem Details, and a client ignores
members it does not know.
`,
  Outcome: `How an execution ended, tagged on \`kind\`. A \`value\` carries the
execution's value as last rendered; while the execution is
running it is the value so far, and it is final once the
execution is \`completed\`. An \`error\` carries the error that ended it.
An \`interrupted\` execution was cancelled before or during execution. Other
kinds are defined by later versions of this protocol.
`,
  Execution: `One cell evaluated within a run, or scratch code evaluated once.
It moves through \`queued\`, \`running\`, and \`completed\`, and ends with
one outcome. Side effects belong to the execution whose context
produced them, and items can arrive after completion while the
execution remains retained. Each new input belongs to a running
execution. Input calls from completed or removed executions raise
\`EOFError\` in the calling code.
`,
  Console: `Text an execution wrote to stdout or stderr. Items are ordinary
objects: a producer replaces one by sending it again with the
same id, and items are removed with their execution.
`,
  Display: `A value an execution showed as a side effect, such as a figure
from \`plt.show()\`. A producer replaces one by sending it again
with the same id, which is how a progress bar updates in place.
`,
  Input: `A running execution's request for a line of text. Its identity,
execution, prompt, password flag, and position stay fixed while
its status tracks the request. The record remains with its
execution after it is answered or cancelled. Submitted answers
travel through the reply endpoint to the runtime.
`,
  InputStatus: `An input starts \`pending\` while it waits for an answer. It becomes
\`answered\` when the host accepts a reply for delivery, or \`cancelled\`
when the host ends the wait while input is still pending. Both
\`answered\` and \`cancelled\` are final. An answered input stays
answered if execution later fails before consuming the value.
`,
  CodeFingerprint: `Opaque code identity assigned by the host. Clients compare cell and execution fingerprints for freshness. Incompatible schemes MUST produce distinct fingerprints.`,
  Etag: `An identifier derived from content, so that every host, kernel,
and store computes the same value for the same state. It is the
first 16 hexadecimal characters, in lower case, of SHA-256 over
the UTF-8 encoding of a canonical text. Each etag says what its
text is; a text made of several values is those values joined by
newlines. Clients do not compute etags. They read them from the
stream and from responses, and send them back as preconditions.
`,
  CellConfig: `How a cell is laid out and whether it runs. Every field is always present, so a cell's etag is well defined.`,
  Cell: `A unit of code and configuration in the document. A cell event
fires when its code, name, or config changes. Markdown and SQL
cells are code that calls \`mo.md\` or \`mo.sql\`; a client chooses
the editor to show.
`,
  Document: `The document as a whole, without its cells, which are their own
objects: the cell order and app config. One per notebook,
and removed with it. The order and the app
config carry their own etags, so an edit to one does not conflict
with an edit to the other, or with edits to cells.
`,
  Event: `A record, removal, or control message from a host stream.
The data is decoded JSON. Snapshot records and reset events omit
the cursor; ready and live events carry it. Unknown event names
belong to later versions or host extensions.
`,
  HostEvent: `A \`host\` event from a host stream.`,
  ProjectEvent: `A \`project\` event from a host stream.`,
  NotebookEvent: `A \`notebook\` event from a host stream.`,
  DocumentEvent: `A \`document\` event from a host stream.`,
  CellEvent: `A \`cell\` event from a host stream.`,
  RuntimeEvent: `A \`runtime\` event from a host stream.`,
  AttachmentEvent: `A \`attachment\` event from a host stream.`,
  RunEvent: `A \`run\` event from a host stream.`,
  ExecutionEvent: `A \`execution\` event from a host stream.`,
  ConsoleEvent: `A \`console\` event from a host stream.`,
  DisplayEvent: `A \`display\` event from a host stream.`,
  InputEvent: `An \`input\` event from a notebook stream.`,
  VariableEvent: `A \`variable\` event from a host stream.`,
  CustomEvent: `A \`custom\` event from a host stream.`,
  ProjectRemovedEvent: `A \`project.removed\` event from a host stream.`,
  NotebookRemovedEvent: `A \`notebook.removed\` event from a host stream.`,
  CellRemovedEvent: `A \`cell.removed\` event from a host stream.`,
  RuntimeRemovedEvent: `A \`runtime.removed\` event from a host stream.`,
  AttachmentRemovedEvent: `A \`attachment.removed\` event from a host stream.`,
  RunRemovedEvent: `A \`run.removed\` event from a host stream.`,
  ExecutionRemovedEvent: `A \`execution.removed\` event from a host stream.`,
  ConsoleRemovedEvent: `A \`console.removed\` event from a host stream.`,
  DisplayRemovedEvent: `A \`display.removed\` event from a host stream.`,
  VariableRemovedEvent: `A \`variable.removed\` event from a host stream.`,
  ResetEvent: `A \`reset\` event from a host stream.`,
  ReadyEvent: `A \`ready\` event from a host stream.`,
  HostMessage: `The data of a \`host\` event. The host object, plus which request caused the event and when.`,
  CustomMessage: `The data of a \`custom\` event. This envelope is standardized; the custom type and payload are defined by their producer.`,
  ProjectMessage: `The data of a \`project\` event. The project as it now is.`,
  NotebookMessage: `The data of a \`notebook\` event. The notebook as it now is.`,
  RuntimeMessage: `The data of a \`runtime\` event. The runtime as it now is.`,
  AttachmentMessage: `The data of an \`attachment\` event. The attachment as it now is.`,
  RunMessage: `The data of a \`run\` event. The run as it now is.`,
  ExecutionMessage: `The data of an \`execution\` event. The execution as it now is.`,
  ConsoleMessage: `The data of a \`console\` event. The item as it now is.`,
  DisplayMessage: `The data of a \`display\` event. The item as it now is.`,
  InputMessage: `The current input record carried by an \`input\` event.`,
  VariableMessage: `The data of a \`variable\` event. The item as it now is.`,
  DocumentMessage: `The data of a \`document\` event. The document as it now is.`,
  CellMessage: `The data of a \`cell\` event. The cell as it now is.`,
  RemovedMessage: `The data of a \`project.removed\`, \`notebook.removed\`,
\`cell.removed\`, \`runtime.removed\`, \`attachment.removed\`,
\`run.removed\`, \`execution.removed\`, \`console.removed\`,
\`display.removed\`, or \`variable.removed\` event. The event name
identifies the kind of object to delete from the client's view.
Removing a notebook also removes its document and cells, and
removing an execution removes its inputs. Clients discard these
child records when they receive the parent's removal event.
`,
  Problem: `An error. Every error response has this one shape, following RFC
9457, and is served as \`application/problem+json\`. \`status\`
repeats the HTTP status, and \`type\` says more precisely what went
wrong. \`decisions\` appears only when \`type\` is
\`tag:marimo.io,2026:host/decision-required\`. A client ignores
members it does not recognize. Hosts redact tokens from errors.
`,
  Decision: `A question the host needs answered before it can carry out a
request. The client answers by repeating the request with
\`decisions\` in the body, mapping this \`id\` to the \`id\` of an
option.
`,
  DecisionOption: `One possible answer to a decision.`,
  CreateNotebookRequest: `The notebook's own fields, minus what the host assigns. A project with a root requires \`path\`; one without requires \`name\`.`,
  UpdateNotebookRequest: `The fields to change. At least one is present.`,
  InputReplyRequest: `The answer to one pending input.`,
  CellConfigInput: `A cell's settings as a client writes them. A field left out takes its default.`,
  CellInput: `A cell as a client writes it. Code must be a string, even when the host withholds source in cell records. Null is not an edit or a request to preserve existing source. The host derives the etags.`,
  PutCell: `Replaces a whole cell, or creates one.`,
  DeleteCell: `Removes a cell.`,
  SetOrder: `Replaces the cell order.`,
  Change: `One change to the document, tagged on \`kind\`.`,
  CellVersion: `A cell's etag, code fingerprint, and version after an edit.`,
  EditResponse: `The document as an edit or save left it, or at a later revision, and the cells it touched.`,
  EditConflict: `The first stale change of an edit or run, and the state the host holds.`,
  SaveRequest: `What a save needs from the client, which is nothing until the host asks a question. \`{}\` is the usual body.`,
  RunRequest: `What to run, exactly one of \`code\` and \`cells\`.`,
  Analysis: `Experimental (analysis). What a document's cells imply, computed together over one
revision of the document so that cross-cell errors agree. One
per notebook, and removed with it. It follows the document it
describes, and \`document_etag\` says which revision that is.
`,
  CellAnalysis: `Experimental (analysis). What a cell's text implies: the names it defines and reads, which
are the edges of the dependency graph, and the errors found in the
text alone or across the set of cells. A pure function of the
code, so two producers compute the same values.
`,
  AnalysisEvent: `Experimental (analysis). A \`analysis\` event from a host stream.`,
  AnalysisMessage: `Experimental (analysis). The data of an \`analysis\` event. The analysis as it now is.`,
};

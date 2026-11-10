# Host protocol

Version 1

The marimo host protocol defines communication between a **host**, a program
that serves notebooks, and a **client**, a program that works with those
notebooks. Clients may provide a user interface or operate headlessly.

A host exposes the **host API** through HTTP endpoints and event streams.
Clients use this API to read notebook state, follow changes, and invoke the
operations the host supports.

To connect, a client needs the API's base URL and an authentication token. The
[local discovery](#local-discovery) mechanism provides these through a record
published by the host. Clients may also obtain them through configuration or
another application.

## Reading this specification

This document describes the notebook model and the behavior expected of hosts
and clients. [OpenAPI](openapi.yaml) defines the endpoints, message formats, and
operation requirements, and is the source for generated types. The
[examples](fixtures/) show complete messages.

Capitalized MUST, MUST NOT, SHOULD, and MAY follow
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174). MUST marks a requirement,
SHOULD a recommendation with justified exceptions, and MAY an option.

The [marimo server](../../marimo/_server/host/) is the reference implementation.

## The notebook model

A **notebook** represents a document together with the results of its reactive
execution. In marimo, cells form a dependency graph, so evaluating one cell can
trigger evaluations of its dependents. Changes to code or inputs can also make
earlier results stale. The notebook presents these relationships alongside its
document and results, allowing clients to follow how changes affect the
computation.

A **runtime** is the kernel that evaluates cells according to their dependencies
and its execution configuration. A host can attach a runtime to produce new
results or serve the document and retained results from storage.

Hosts advertise their capabilities as a set of operations, which clients use to
determine what they can do with a notebook. A client can read a document and
its saved results, then offer editing or execution when those operations are
available. Hosts MAY choose their own storage and runtime arrangements while
presenting the same notebook model and API to clients.

A host can serve a document and saved results without a Python runtime,
then attach one when a client needs to execute code.

- **Snapshot hosts** serve documents and results from previous runs. A small
  web server could expose these through the host API for a client to display in
  a webview, without running Python.

- **Session hosts** keep a runtime attached while clients work with a notebook,
  as in a typical `marimo edit` session.

- **Hosts with on-demand runtimes** support editing and viewing saved results,
  provisioning a kernel when a client requests execution.

### Projects and identity

A **project** groups notebooks that a host presents together. It may correspond
to a directory or a collection managed by the host.

A notebook's identity is independent of its storage. Notebooks in the host's
catalog may be backed by files, stored in a database, or held in memory. A host
can expose a fork as a new notebook before deciding whether or where to persist
it. A host MUST preserve a notebook's identity while serving it, including
across renames and moves.

### Documents and cells

The **document** is the notebook's editable source, organized into **cells**.
Each cell holds code and the information used to present and execute it. The
document and each cell carry an **etag**, derived from their content, and a
**version**. The document's version counts its changes. A cell's version is
the document version at which the cell was created or last changed, so of two
records of a cell, the higher version is the newer. Versions are comparable
only within one notebook.

`code_fingerprint` is an opaque code identity assigned by the host. Clients
compare it with an execution's fingerprint when checking freshness.
Formatting-only edits MAY preserve it. Edits to source, name, or config change
the cell etag. Cells and executions MUST use compatible fingerprint schemes;
incompatible schemes MUST produce distinct fingerprints.

A host MAY withhold a cell's source by publishing `code: null`. The field MUST
remain present; an empty string is an empty cell. Fingerprints MUST be computed
from the actual source. Source visibility MUST NOT change fingerprints, etags,
or versions.

Hosts MUST apply their source visibility policy consistently to snapshots,
live events, replay, and responses containing cells. `hide_code` controls
presentation, while the source visibility policy determines the `code` sent
to clients. Hashes, outputs, diagnostics, and other protocol data may still
reveal information about withheld source.

### Runtimes and attachments

Clients connected to a notebook share its document and runtime. Hosts MUST
expose at most one runtime per notebook. A fork with an independently editable
document or a separate concurrent runtime MUST appear as another notebook, even
when both originate from the same file. Restarting a notebook's runtime
preserves the notebook's identity.

Hosts MAY seed a new notebook from an existing document and retained results,
choosing how it is stored and which operations each client can use. Several
clients can share a notebook while only some are permitted to edit or save it.

An **attachment** represents a client's connection to a notebook. It belongs to
the notebook and remains connected across runtime restarts. Each opening of a
notebook's event stream MUST create a separate attachment, removed when that
connection closes, including when reconnecting with `Last-Event-ID`.

When opening a stream, clients MAY supply `Marimo-Attachment-Identity`,
`Marimo-Attachment-Kind`, and `Marimo-Attachment-Name`. Hosts expose these as
`identity`, `kind`, and `name` on the attachment, as defined in the OpenAPI
schema. A shared identity lets clients group attachments across streams and
reconnects. Each attachment keeps its own id and connection lifetime.

Stopping a runtime ends its active and queued work, completing those runs as
`interrupted`, and loses its Python state, while the document and retained
results remain available to clients.

### Runs and results

A **run** groups a cycle of work and the reactive evaluations it causes. An
**execution** records an individual cell evaluation or scratch computation
within that cycle. Clients can follow individual execution results and the
overall progress of a run.

```text
Notebook
│
├── Run A · evaluate a cell
│   ├── Cell execution · the requested cell
│   ├── Cell execution · a dependent cell
│   └── Cell execution · another dependent cell
│
└── Run B · evaluate scratch code
    └── Scratch execution
```

Runs and executions move through `queued`, `running`, and `completed`.
Hosts MUST complete a run only after its executions have ended and scheduling
for that cycle has finished. An error in one execution may occur while others
are still working. An execution that did not evaluate because of other work in
the notebook, such as a dependent of a cell that raised or that stopped the
cycle on purpose, or a queued execution that a later one of the same cell
replaced, completes with the outcome `skipped`, which names the reason and the
cells involved. A skipped execution has no value, binds no variables, and does
not fail its run.

A host publishes an execution as `queued` when the runtime schedules the cell,
including work the run discovers as it goes, such as cells a state update marks
for another evaluation. The execution's cell and code fingerprint are fixed from
then on. A queued execution that will not run completes without starting, as
`skipped` or `interrupted`.

An execution can also lead to a later run. For example, a cell may create a UI
element that a user later interacts with, triggering reactive evaluation. That
work belongs to a new run and does not extend the original run's lifetime.

```text
Notebook
│
├── Run A · evaluate a cell
│   └── Cell execution A1 · create a UI element
│
└── Run B · respond to a later UI interaction
    ├── Cell execution · a dependent cell
    └── Cell execution · another dependent cell
```

An execution's results include its outcome, **console** output, **display**
items, **inputs**, and the **variables** a cell bound. Results can remain
available after the runtime stops or be restored from storage. Hosts choose
how long to retain results and SHOULD keep ephemeral results briefly after
completion to allow reconnection.

Console, display, and input items share a `seq` ordering within their
execution, so a client can place prompts among the outputs that surround them.
Background work may continue producing console and display items after the
execution completes, as long as its results remain retained. Input requires a
running execution, because the host must still be able to accept an answer or
interrupt the work that is waiting for it.

### Inputs

An **input** records an execution's request for a line of text, such as a call
to Python's `input()` or `getpass.getpass()`. It gives clients a prompt to
display and a status indicating whether an answer is still needed.

    Input { id, execution_id, seq, prompt, password, status }

Hosts MUST assign each prompt a distinct item id across executions and runtime
restarts. Its execution, prompt, password flag, and position stay fixed while
its status records the progress of the request.

| Status | Meaning |
| --- | --- |
| `pending` | The input is waiting for an answer. |
| `answered` | The host accepted a reply for delivery to this input. |
| `cancelled` | The host ended the wait while the input was still pending. |

An input starts `pending` and can transition once to `answered` or `cancelled`.
An answered input stays answered if execution later fails before consuming the
value, because its status records that the host accepted the reply.

The execution remains `running` while it waits, and clients determine whether
it needs input by looking for pending inputs. Hosts MUST cancel any remaining
pending inputs before publishing the execution as completed, including on
interruption, runtime stop, restart, or failure.

Inputs stay with their execution after they are answered or cancelled, so a
reconnecting client can distinguish outstanding prompts from those already
resolved. Inputs retain their state through output clearing and client
disconnections.

When `password` is true, clients MUST obscure the answer as it is entered.
Hosts MUST restrict input records, input events, and reply responses to the
prompt's identity, metadata, and status. Submitted answers travel through the
reply endpoint to the runtime, where user code may expose them through outputs
or variables.

### Variables and result freshness

A **variable** is a name in the notebook's namespace whose value varies over
time. A cell's execution **binds** variables as it ends, each with a
**revision** of its value. An **update** advances a revision without binding
again, as when a state setter runs or a client sets a value. A revision names
the execution whose evaluation produced the value and counts the updates
since. Clients compare revisions for equality.

    Variable  { id, execution_id, name, revision, type, preview }
    Revision  { execution, update }

Hosts MUST publish a cell execution's variables before its `completed` status,
and MUST remove a cell's previous execution and its items before publishing
the next one, which they do only once the previous one has completed. A cell
has one latest execution on the stream and at most one that is not completed.

An execution's `depends_on` records the variable revisions its result is valid
against. A name that no retained cell execution had bound is recorded as null.

    Execution { ..., depends_on: Record<Name, Revision | null> }

A completed cell execution is **current** when all of the following hold.

- its `code_fingerprint` equals the cell's,
- each variable it depends on still holds the recorded revision,
- each name it depends on that was unbound is still unbound,
- the execution that bound each of those variables is current.

A client looks up each dependency by name, and also by the recorded revision's
`execution` unless it is null. A dependency was replaced if no variable matches
its revision, or if a variable now has a name recorded as null. It was updated
if the variable's `update` is higher. An execution was edited if its
`code_fingerprint` differs from its cell's. A result whose dependency was bound
by an outdated execution is outdated for the same reason. The first of replaced,
updated, and edited that applies is why the result is **outdated**.

A cell without an execution has no result to compare. A skipped execution
records the dependencies it would have read and is compared like any other.
Scratch executions run in a local namespace, bind no variables, and are not
compared.

For example, cell `k7f2` reads `x`, which cell `c3` binds.

    Cell c3     code_fingerprint 0f71…   Execution e12   code_fingerprint 0f71…   depends_on {}
    Variable x  revision {e12, 0}  bound by e12
    Cell k7f2   code_fingerprint db2b…   Execution e13   code_fingerprint db2b…   depends_on {x: {e12, 0}}

Both executions are current. An update that advances `x` to `{e12, 1}` makes
`e13` outdated because a value it depends on was updated. Editing `c3` makes
`e12` outdated because its code changed, and `e13` because the execution that
bound `x` is. Running `c3` again removes `e12` and binds `x` under a new
execution, so `e13` is outdated because the execution it depends on was
replaced.

The runtime stamps `depends_on` as the execution ends, using the following
rules to describe the values in its namespace.

- a value the execution itself updated is recorded at the revision it set,
- a name bound only by a result from an earlier runtime is recorded as
  unbound,
- a value carried forward unchanged, such as an import, keeps its revision,
  so a revision's `execution` can be earlier than the variable's
  `execution_id`.

Updates are published before any execution that depends on them. The host
removes the runtime when its process ends, so a result is **live** when its
`runtime_id` is the notebook's runtime.

## Connecting to the host API

Clients connect using the host API's base URL and bearer token, whether
supplied through configuration or [local discovery](#local-discovery). Version
1 serves the API over HTTP on loopback addresses. Hosts MUST authenticate
requests using the token and accept only loopback connections.

## Following state

Clients use **event streams** to read state and follow changes as they happen.
The **catalog stream** describes the host's notebooks and resources. A
**notebook stream** carries the document and results for one notebook.

A record event carries the object's current state and replaces any earlier
record with the same identity. For example, an `input` event first introduces
a pending prompt, then replaces it with the answered or cancelled record.
Removal events tell clients which records to discard. Clients handle
`execution.removed` by discarding both the execution and its inputs.

On an initial connection, the host sends a **snapshot** as a sequence of events
describing the current state. For a notebook, these events include its cells,
document, and retained results, with executions before their items. A `ready`
event marks the end of the snapshot, after which the stream delivers changes
as they happen. A client that only needs the current state can disconnect at
`ready`.

Clients can select object kinds with `types`. On a notebook stream, `run_id`
narrows the view to one run and its executions and items. Because filters also
select removal events, a client retaining inputs MUST subscribe to both `input`
and `execution` to learn when those inputs are removed. The same filters apply
to snapshots, live events, and replay.

A notebook snapshot MUST represent one consistent state. Hosts MUST publish
each document change as a group without interleaving unrelated events, so
clients can apply an edit together with its effects on the rest of the
document.

Each **cursor** marks a position in the stream. Clients treat cursors as
opaque. A client sends back the last cursor it received and does not compare
or construct cursors. After disconnecting, a client can reconnect with its last
cursor to request the events it missed. If the host no longer has those events,
or the cursor predates a loss of host state, it requests a reset. Clients MUST
then discard their previous view and rebuild it from a fresh snapshot.

Event history can expire while results remain stored. Those results still
appear in a fresh snapshot, even when their original events are unavailable.

This version carries event streams over server-sent events (SSE). Other
transports, such as WebSocket, could carry the same events while preserving
their ordering, snapshot, and replay guarantees.

### Custom events

A **custom event** describes an occurrence in a notebook without creating or
updating an object. Hosts MAY send custom events on the notebook stream using
the `custom` event kind. The protocol defines their envelope, while the
producer defines the meaning and JSON payload of each namespaced `type`, such
as `marimo.pair.agent-message`. Producers MUST use a namespace they control.
Clients MUST ignore custom types they do not recognize while retaining the
stream cursor. Consumers of a type are responsible for validating its payload.

Custom events MUST carry a timestamp, with the notebook identified by the
stream. The envelope MUST include `request_id` when a request caused the event
and omit it otherwise. Custom events participate in the stream's ordering and
cursor-based replay, with their original ids and timestamps. They MUST NOT
appear in snapshots. Once their replay history expires, a
reset cannot recover them. Features that need recoverable state MUST
represent that state separately rather than relying on custom events alone.

`types=custom` selects custom events, regardless of their namespaced type.
Custom events do not belong to a run and are excluded when `run_id` is set.
They do not appear on the catalog stream.

## Editing and running notebooks

### Capabilities

An **operation** is an action the host offers. The host advertises its
supported operations, while projects and notebooks advertise those permitted
for each object. Hosts MUST base these capabilities on permissions rather than
transient state. For example, a notebook can permit execution while its runtime
is stopped. A client uses the notebook's current state to determine what
preparation is needed before calling an operation.

Hosts MUST authorize `runtime.run`, `runtime.execute`, and `notebook.edit`
independently. A notebook may permit rerunning its cells without permitting
edits or scratch execution.

Source visibility and editing permission are independent. A client MAY display
available source without `notebook.edit`. An editor for existing source needs
both a non-null `code` and permission to edit. Withholding source does not
remove the notebook's execution records, outputs, or runtime state.

### Requests and decisions

Requests can produce changes after their HTTP response has arrived. The host
includes a client-supplied request key in related events, allowing clients to
follow the effects of their actions on the shared notebook stream.

The same key makes a request safe to retry within the host's documented retry
window. Once a request is accepted, hosts MUST recognize its retries within that
window and avoid repeating the work. This guarantee is separate from how long
results are kept and does not extend beyond the retry window or a loss of host
state.

Some operations require a **decision**, such as choosing a kernel environment
or resolving a change to the backing file. The host returns the available
choices in a problem response. The client can present them to a user or answer
automatically, then submit the request with its choice and a new key.

### Editing and saving

Edits describe a group of changes to the document. Hosts MUST apply each group
atomically and reject the whole group if its preconditions are stale. Clients
can inspect the conflicting state and decide how to revise their edit.

`put_cell` replaces the whole cell and MUST include string-valued source in
`CellInput.code`. A client MUST NOT round-trip a withheld `code: null` as an
edit or substitute an empty string for it. Other changes, such as reordering
or deleting cells, do not require source but still require editing permission.

Preconditions use **etags**, identifiers derived from content. They let clients
edit different parts of a document independently while detecting competing
changes to the same part. For example, two clients can update different cells,
but an edit based on an older version of the same cell produces a conflict.
An accepted edit answers with the version of each cell it touched and the
document at the edit's revision or a later one. The client already has the
content it sent, and the versions let it recognize the edit when its events
arrive on the stream.

Accepting an edit and saving it are separate actions. The host reports whether
the current document has reached storage, whether it saves automatically or
offers an explicit save operation. Changes made during saving, such as code
formatting, MUST reach clients through the document stream as well.

### Execution

`runtime.run` runs notebook cells by id. A client can include each cell's `etag`
to run it only if its code, name, and settings still match what the client read.
The runtime's execution settings determine which dependent cells run too.
A dependent left out keeps its execution, which becomes outdated when an
execution it depends on is replaced.

`runtime.execute` evaluates Python with access to the notebook's current
values without adding a cell. It uses a copy of the runtime's variables, so
new variables and assignments stay within the call. The objects themselves
are shared. Changing a list or dataframe can therefore affect the notebook.

Marimo hosts provide the internal `marimo._code_mode.get_context()` API within
`runtime.execute`. It exposes notebook cells and captured outputs, along with
methods for editing and running cells. The outputs are captured when execution
begins.

An accepted execution request starts a run whose progress and results arrive on
the notebook stream for all attached clients. Clients that need to observe the
full sequence open the stream before submitting work. Hosts that offer execution
MUST execute one run at a time, accept further requests as `queued` runs, and
start them in the order they were accepted. A run's requested cells and their
source are fixed when it is accepted, and the run's `cells` names them, so a
client can tell which cells a queued run will reach before the runtime has
planned their executions. Editing continues while runs are queued or running,
and a result from source the document no longer has is outdated.
Completion means the work has finished, including any interruption that was
requested.

### Cancelling a run

Hosts offering `runtime.run` or `runtime.execute` MUST support
`runtime.cancel`. Clients target one run without affecting other runs or
stopping the runtime.

```http
DELETE /notebooks/{notebook_id}/runtime/runs/{run_id}
Idempotency-Key: cancel-1
```

This request has no body. A queued run MUST be removed from the queue and
complete `interrupted` without executing. For a running run, the host MUST
interrupt only if that run is still active, and its remaining executions MUST
end `interrupted`. If the target finishes before cancellation takes effect,
the host MUST NOT interrupt a successor. Pending inputs belonging to cancelled
work MUST be cancelled. Other runs MUST remain untouched.

A completed run receives `conflict`, so a client attempting cancellation can
distinguish work that already finished. An accepted request receives `202`
with the `Run`; this acknowledges cancellation, not completion. The notebook
stream reports the run and execution outcomes once they settle. Retrying an
accepted request follows the protocol's idempotency rules, including after
the run completes.

### Answering input

When running code requests input, the host MUST publish a pending input and
wait for an answer or cancellation. This applies to cell, scratch, and reactive
executions. Hosts MUST associate each new input with a running execution.
Input calls from completed or removed executions MUST raise `EOFError` in the
calling code, including calls from background work that outlives its execution.

Hosts offering `runtime.run` or `runtime.execute` MUST implement
`runtime.input`. Any client permitted the operation may answer. This permission
applies to the notebook and is independent of which client started the run or
opened an event stream.
The client sends the input id in the URL and its answer in the request body.

```http
POST /notebooks/{notebook_id}/runtime/inputs/{input_id}/reply
Idempotency-Key: reply-1
Content-Type: application/json

{ "value": "Trevor" }
```

The runtime receives the text in `value` exactly as submitted, including an
empty string when the answer is empty. Clients that want to stop the work
waiting for input can cancel its run.

The host MUST accept at most one reply to each input and reject replies once
it is cancelled. Before acknowledging a reply, the host MUST arrange delivery
to that specific input and publish its `answered` record. The response confirms
acceptance, and clients follow execution events to observe further progress.
If delivery subsequently fails, the host MUST end the execution with an error
or interruption.

Replies follow the protocol's [idempotency rules](#requests-and-decisions).

| Request | Response |
| --- | --- |
| First accepted reply | `200` with the answered input record. |
| Retry with the same key and request within the retry window | The original response for the accepted reply, including after execution removal. |
| New reply to an answered or cancelled input | `409 conflict`. |
| Reply to an unknown, removed, or other notebook's input | `404 not-found`. |

An input's creation event carries the execution's originating request key.
The answered event carries the reply's key, and cancellation carries the
cancelling request's key when there is one. Subsequent run and execution events
keep their original request key, so clients can continue following the run
independently of its answers.

## Local discovery

Local discovery lets clients find running hosts without asking a user for a URL
and token. A participating host publishes a **host record** under
`<marimo-state-dir>/hosts-v1/` once its API is ready, and removes it when it
stops. The record provides the connection details and identifies the process
serving the API.

A record grants access to a host, so clients MUST verify that it is private to
the current user and belongs to a running process before trusting it. Records
can survive a crash. A record whose process has ended is stale and MAY be
removed.

## Compatibility and conformance

Hosts can extend the protocol with new capabilities. Clients MUST ignore
unfamiliar fields, operations, and events while continuing to process the parts
they understand. A breaking change requires a new record version and API base
path. Protocol versions are independent of marimo releases.

Conformance tests exercise the contract from a client's perspective. Hosts,
including marimo's reference implementation, are responsible for the common
requirements and the semantics of every operation they advertise, including
behavior not yet covered by tests.

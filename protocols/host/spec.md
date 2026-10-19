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

Executing code requires a Python runtime, but serving a document and saved
results does not. This gives hosts a range of implementation choices, for
example:

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

A host MAY also publish an **analysis** of the document: each cell's
definitions, references, and problems, so clients can understand a cell's role
in the computation and identify problems before execution. Because cells share
a dependency graph, editing one can affect the analysis of others. An analysis
therefore covers the whole document and names the revision it describes. Hosts
publish it after that revision of the document.

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
schema. Consumers can use a shared identity to group attachments from the same
client across streams and reconnects. Each attachment still has its own id and
lifetime; identity does not merge connections or keep an attachment alive.

Stopping a runtime ends its active work and loses its Python state, while the
document and retained results remain available to clients.

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

Hosts MUST complete a run only after its executions have ended and scheduling
for that cycle has finished. An error in one execution may occur while others
are still working.

An execution can also lead to a later run. For example, a cell may create a UI
element that a user later interacts with, triggering reactive evaluation. That
work belongs to a new run, which can identify the earlier execution as its cause
without extending the original run's lifetime.

```text
Notebook
│
├── Run A · evaluate a cell
│   └── Cell execution A1 · create a UI element
│
└── Run B · respond to a later UI interaction (Run.caused_by = A1)
    ├── Cell execution · a dependent cell
    └── Cell execution · another dependent cell
```

Results include an execution's outcome, **console** output, **display**
items, and the **variables** a cell's execution bound. They can remain
available after the runtime stops or be restored from storage. Hosts choose
how long to retain results and SHOULD keep ephemeral results briefly after
completion to allow reconnection.

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
the next one. A cell has one latest execution on the stream.

An execution **depends on** the variables it used, each at the revision the
runtime holds its result valid against. A name that no retained cell
execution had bound is recorded as null.

    Execution { ..., depends_on: Record<Name, Revision | null> }

A completed cell execution is **current** when:

- its `code_hash` equals the cell's,
- each variable it depends on still holds the recorded revision,
- each name it depends on that was unbound is still unbound,
- the execution that bound each of those variables is current.

A client finds a variable by the recorded revision's `execution` and the name.
If none exists, that execution was replaced or removed. If its `update` is
higher, the value was updated. If that execution's `code_hash` differs from
its cell's, the cell was edited. The first that applies is why the result is
**outdated**. A cell with no execution has no result to compare. Scratch
executions have no cell and are not compared.

For example, cell `k7f2` reads `x`, which cell `c3` binds:

    Cell c3     code_hash 0f71…   Execution e12   code_hash 0f71…   depends_on {}
    Variable x  revision {e12, 0}  bound by e12
    Cell k7f2   code_hash db2b…   Execution e13   code_hash db2b…   depends_on {x: {e12, 0}}

Both executions are current. An update that advances `x` to `{e12, 1}` makes
`e13` outdated because a value it depends on was updated. Editing `c3` makes
`e12` outdated because its code changed, and `e13` because the execution that
bound `x` is. Running `c3` again removes `e12` and binds `x` under a new
execution, so `e13` is outdated because the execution it depends on was
replaced.

The runtime stamps `depends_on` as the execution ends, from its own namespace
and rules:

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

On an initial connection, the host sends a **snapshot** as a sequence of events
describing the current state. For a notebook, these events include its cells,
document, and retained results. A `ready` event marks the end of the snapshot,
after which the stream delivers changes as they happen. A client that only
needs the current state can disconnect at `ready`.

A notebook snapshot MUST represent one consistent state. Hosts MUST publish
each document change as a group without interleaving unrelated events, so
clients can apply an edit together with its effects on the rest of the
document.

Each **cursor** marks a position in the stream. After disconnecting, a client
can reconnect with its last cursor to request the events it missed. If the host
no longer has those events, it requests a reset. Clients MUST then discard
their previous view and rebuild it from a fresh snapshot.

Event history can expire while results remain stored. Those results still
appear in a fresh snapshot, even when their original events are unavailable.

This version carries event streams over server-sent events (SSE). Other
transports, such as WebSocket, could carry the same events while preserving
their ordering, snapshot, and replay guarantees.

### Custom events

A **custom event** describes an occurrence in a notebook without creating or
updating an object. Hosts MAY send custom events on the notebook stream using
the `custom` event kind. The protocol defines their envelope; the producer
defines the meaning and JSON payload of each namespaced `type`, such as
`marimo.pair.agent-message`. Producers MUST use a namespace they control.
Clients MUST ignore custom types they do not recognize while retaining the
stream cursor. Consumers of a type are responsible for validating its payload.

The stream identifies the notebook. Custom events MUST carry a timestamp.
When a request causes a custom event, the envelope MUST carry that request's
key in `request_id`; otherwise, the key is omitted. They participate in the
stream's ordering and cursor-based replay, with their original ids and timestamps.
They MUST NOT appear in snapshots. Once their replay history expires, a
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

Preconditions use **etags**, identifiers derived from content. They let clients
edit different parts of a document independently while detecting competing
changes to the same part. For example, two clients can update different cells,
but an edit based on an older version of the same cell produces a conflict.
An accepted edit answers with the document and the version of each cell it
touched. The client already has the content it sent, and the versions let it
recognize the edit when its events arrive on the stream.

Accepting an edit and saving it are separate actions. The host reports whether
the current document has reached storage, whether it saves automatically or
offers an explicit save operation. Changes made during saving, such as code
formatting, MUST reach clients through the document stream as well.

### Execution

Clients can request document cells or submit scratch code. Cells execute under
the runtime's execution configuration, which determines how dependent cells
are scheduled. A dependent the configuration leaves out keeps its execution,
which is outdated once a new execution replaces the one it depends on. Scratch
code runs against a copy of the runtime namespace outside the document's
dependency graph. A client can ask the host to verify that a cell's code still
matches what it read before executing it.

An accepted execution request starts a run whose progress and results arrive on
the notebook stream for all attached clients. Clients that need to observe the
full sequence open the stream before submitting work. Hosts MUST limit each
notebook to one run in progress and support interruption when they offer
execution. Completion means the work has finished, including any interruption
that was requested.

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

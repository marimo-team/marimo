# Document analysis

An **analysis** describes a document's definitions, references, and problems,
so clients can understand its dependency graph and identify problems before
execution. Because editing one cell can affect others, analysis covers the
whole document at one revision.

An analysis is current while its `document_etag` matches the document's `etag`.
A change to that etag makes the analysis stale, including results for cells
whose source did not change. Execution and runtime restarts do not themselves
invalidate analysis. Clients MUST NOT treat stale analysis as describing the
current document.

Hosts MAY publish analysis on the notebook stream, after the document it
describes. Each analysis replaces the previous one in full and is retained
until replaced or the notebook is removed. Snapshots include the latest
available analysis, which may be stale. Computation may finish after `ready`;
receiving `ready` does not guarantee analysis of the current document.

The [overlay](overlay.yaml) defines the message formats and diagnostics.
The [examples](fixtures/) show complete messages.

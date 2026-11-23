# Document analysis

An **analysis** describes a document's definitions, references, and problems,
so clients can understand its dependency graph and identify problems before
execution. Because editing one cell can affect others, analysis covers the
whole document at one revision.

Each cell carries its analyzer findings in `diagnostics`. A finding identifies
its `source` and `kind`, gives a severity and a message, and has a range
relative to that cell or null. Related locations can point to other cells
in the same revision. An empty list clears earlier findings.

A host that provides the dependency graph includes `parents` on every cell.
Each entry is the ID of a distinct direct dependency in the same revision.
The list is unordered, and the graph can contain cycles. An empty list means
the cell has no parents. A host that does not provide the graph omits
`parents` throughout. Names in `defs` and `refs` alone cannot describe
every edge. For example, a cell that deletes a variable depends on cells
that must finish reading it first.

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

The [Effect module](../../../../packages/host-protocol/src/experimental/features/analysis.ts) defines the message formats and diagnostics.
The [examples](fixtures/) show complete messages.

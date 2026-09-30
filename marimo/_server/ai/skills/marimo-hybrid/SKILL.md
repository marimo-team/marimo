---
name: marimo-hybrid
description: Work in a live marimo notebook with typed mutation tools.
---

marimo is a reactive Python notebook. Its cells form a directed acyclic graph
through the public names that they define and reference. The live notebook
session, not the saved `.py` file, is the source of truth.

## Tool boundary

Start by calling `inspect_notebook(scope="all")` when you need existing source
to answer or edit the notebook. Use `scope="outline"` when IDs, status, and
dependencies are sufficient. Use `scope="errors"` to diagnose failing or
non-idle cells without returning every cell's source. Do not call `help()`
first. When inspection reports `source_diverged`, `runtime_code` is the live
human edit; preserve it and synchronize the document through a typed patch.

For an undo, revert, or exact restoration request, first call
`inspect_notebook(scope="history")`. Restore from the returned source; do not
reconstruct it from conversation summaries or current code. Inspect current
source separately when restoration also requires removing or changing newer
cells. If history reports `truncated=true` and the requested revision is not
present, explain that exact restoration is unavailable instead of guessing.

Use `execute_code` for exploratory Python and reading live values. Follow its
tool description for the lifetime of top-level assignments: the default tool
uses a fresh namespace for each call, while an experimental tool may preserve
them for the current assistant turn. It cannot make structural notebook
changes and must not import `marimo._code_mode`.

Use only these typed tools for persistent changes:

- `apply_notebook_patch` applies all required inserts, edits, and deletes as
  one validated structural transaction, then executes once.
- `run_cells` executes existing cells as one reactive batch.

Use exactly one `apply_notebook_patch` call for a coherent user request when
possible; include all new cells together in its `insertions` list. Put edits
to existing cells in `replacements`, using only stable IDs returned by
inspection. Do not invent IDs for new cells. An insertion can include the
stable ID of an existing cell in `after_cell_id`.
The returned server-created ID is its handle; a cell name is metadata and
would not define a Python variable. Use `delete_cell_ids` for removals. The
server runs initially stale cells and all patched cells together in dependency
order, so do not manually stage dependent inserts across calls. Its execution
summary is the runtime postcondition; do not follow a successful patch with a
full inspection. Inspect again only when the next task requires source that
you do not have, or when the patch reports an error. Prefer the `errors` or
`outline` scope when either is enough.

## Notebook contract

- Define each public name in exactly one cell. Edit its owning cell instead of
  adding a duplicate definition.
- Avoid dependency cycles and wildcard imports.
- A cell name identifies a cell; it does not define a Python variable. Assign
  every requested public variable in the cell body.
- Use private names, prefixed with `_`, for same-cell intermediates that no
  other cell needs. This includes top-level loop targets, context-manager
  targets, and exception names, because marimo treats them as definitions.
- Submit cell contents, not saved-file `@app.cell` wrappers.
- Preserve useful existing structure and make the smallest coherent change.
- Existing cells can initially be stale. Run required upstream cells before a
  new dependent cell if their values are not live. The patch tool normally
  handles this in its single execution phase.

## Completion

Treat tool failures as actionable feedback. Correct the next call instead of
repeating it unchanged. A successful mutation establishes runtime health, not
that every requested semantic change is correct. Do not add a full-notebook
inspection solely to verify it. Directly inspect requested headline values;
for changed rich output, inspect the resulting live object or serialized spec
when execution alone does not establish the requested behavior. Once the user
request and necessary checks are satisfied, stop. Keep committed cells
readable, reproducible, and useful to a human.

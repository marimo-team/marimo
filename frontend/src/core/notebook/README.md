# Notebook state

A notebook brings together its document, execution results, runtime, and
attachments. This follows the ownership model in `marimo/_core/notebook.py`.
The frontend reads confirmed state and layers local edits over it.

| Module | Responsibility |
| --- | --- |
| `replica/` | Backend-confirmed state, resource reducers, and stream recovery. Independent of React and application implementations. |
| `document/` | Local drafts, edit submission, synchronization, and document hooks. |
| `attachments.ts` | Selectors and hooks for the active notebook's attached clients. |
| `../session/` | Backend selection, active replica ownership, startup, and cleanup. |
| `../transports/` | WebSocket, SSE, WASM, and static adapters. |

React consumers import `useNotebook*` hooks from `@/core/notebook`:

```tsx
import {
  useNotebookAttachments,
  useNotebookCellCode,
  useNotebookDocumentEdit,
} from "@/core/notebook";

const code = useNotebookCellCode(cellId);
const agents = useNotebookAttachments("agent");
const edit = useNotebookDocumentEdit();
```

Document hooks read a model supplied by `DocumentProvider`. The model's owner
controls its abort signal; mounting the provider does not start another model.
Attachment hooks select the replica published by the mounted session.
`session/state.ts` stores that active instance; resource selectors live here.

Construction code imports the interfaces at `@/core/notebook/replica` and
`@/core/notebook/document`. Their internal files remain private, enforced by
`marimo/module-entry`. The replica's dependency restrictions are enforced by
`marimo/replica-imports`.

## Extending the notebook

Execution resources belong to the confirmed notebook state. When introduced,
the replica should compose their reducers alongside document and attachment
resources; execution selectors and hooks belong in `notebook/executions/`
and are exposed through this module's entry point. Results can outlive the
runtime that produced them. There is no executions module here yet.

Keep confirmed state, local editing state, and view state distinct. Reconnecting
the stream should not end the editing lifetime. Editor handles, selection,
focus, and scrolling belong to the view. The existing `core/cells` state still
contains view and execution state; this organization does not migrate it or
change the current notification handling.

# Keep state from events

Host state is read over event streams. The catalog stream describes the
host's notebooks, projects, runtimes, and attachments. A notebook stream
describes one notebook's document and execution state.

A stream starts with a snapshot of the current state. A `ready` event marks
the end of the snapshot. Subsequent events report changes. For example, a
`notebook` event carries the notebook's current record, and
`notebook.removed` identifies a notebook that was removed.

`CatalogEvents` and `NotebookEvents` validate incoming events and track the
cursor used to resume after a disconnect. They deliver events through an
async iterator or a subscription. Your application decides which records
to retain. If the stream cannot resume, it delivers `reset` followed by a
new snapshot that replaces the previous state.

## Keep a notebook list

To keep a notebook list, define a resource that starts with an empty list.
Its `notebook` handler adds or replaces an entry. Its `notebook.removed`
handler removes an entry by id. Each entry keeps only the notebook's id
and name.

Pass the resource to `createCatalogReducer`, then apply each event with
`reduce(state, event)`. The resulting list is in `state.resources.notebooks`.
This example stops at `ready` and prints the list from the snapshot.

```ts
import type { NotebookOutput } from "@marimo-team/client/protocol";
import {
  Client,
  createCatalogReducer,
  type CatalogResource,
} from "@marimo-team/client";

type NotebookSummary = Pick<NotebookOutput, "id" | "name">;

const notebooks: CatalogResource<readonly NotebookSummary[], "notebook"> = {
  initial: [],
  on: {
    notebook: (state, { data }) => [
      ...state.filter((entry) => entry.id !== data.notebook.id),
      { id: data.notebook.id, name: data.notebook.name },
    ],
    "notebook.removed": (state, { data }) =>
      state.filter((entry) => entry.id !== data.id),
  },
};

const reducer = createCatalogReducer({ notebooks });
const client = new Client("http://127.0.0.1:2718/api/marimo/v1", {
  token: "your-token",
});
let state = reducer.initial;

for await (const event of client.events({ types: ["notebook"] })) {
  state = reducer.reduce(state, event);
  if (event.event === "ready") break;
}

console.log(state.resources.notebooks);
```

The reducer handles the stream's lifecycle. `ready` changes `state.phase`
from `snapshot` to `live`. `reset` returns the phase to `snapshot` and each
resource to its initial value. Resources can handle `ready` to finish
assembling a snapshot. The handler's third argument contains the phase
before the event is applied. It is `snapshot` for the initial `ready` and
`live` for a `ready` that follows a resumed connection.

Handlers return a new value when state changes and the existing value
otherwise. They must not modify the previous value or perform side effects.

For a notebook stream, define a `NotebookResource` and pass it to
`createNotebookReducer`. This reducer also keeps the notebook's record and
identity in `notebook` and `notebookId`. It handles `notebook` and
`notebook.removed` itself. Removing the notebook clears its record and
resources. A `reset` also clears its identity.

## Follow changes in React

To keep a notebook list updated in a UI, subscribe to the stream and pass
each event to the reducer through your store's state update function. This
hook uses React state. It removes the subscription and closes the stream
when the effect is cleaned up.

```tsx
import { useEffect, useState } from "react";

function useNotebooks(client: Client) {
  const [state, setState] = useState(reducer.initial);

  useEffect(() => {
    setState(reducer.initial);
    const events = client.events({ types: ["notebook"] });
    const unsubscribe = events.subscribe((event) => {
      setState((current) => reducer.reduce(current, event));
    });
    return () => {
      unsubscribe();
      events.close();
    };
  }, [client]);

  return state;
}
```

Keep the client instance stable across renders. Temporary disconnects preserve
state while the stream resumes. A `reset` rebuilds it. `events.closed` rejects
if the stream stops with an error, so you can use it to surface connection
failures in your application.

If you persist state for a later connection, save its matching cursor and
reuse the same host, stream, and filter. The stream's cursor tracks received
events. When state updates are queued, as in React, it can be ahead of the
state you have applied. Resume needs both state and its matching cursor.

# OpenCode inbox setup

Notebook agent messages require OpenCode 2.x on macOS or Linux.
Enable the host protocol on the marimo server:

```sh
MARIMO_ENABLE_HOST=1 uvx marimo@latest edit notebook.py
```

Use a native OpenCode conversation backed by its registered local service.
Ask OpenCode to run this command in its shell tool, from the conversation's project directory:

```sh
uvx marimo@latest pair connect --url http://localhost:2718 --notebook <notebook-id> --harness opencode
```

Use the backend URL printed by marimo. In a development checkout, this differs
from the Vite frontend URL. Get the Notebook ID from `marimo pair notebook list --url <url>`
or the notebook's Pair with agent dialog.

Pair reads the private `$XDG_STATE_HOME/opencode/service.json` record
(`~/.local/state/opencode/service.json` by default). It verifies the service
PID and version through `/api/info`, then uses the native `OPENCODE_SESSION_ID`
export when available. Otherwise, it matches a running shell PID to the connect
process's ancestry and reads the conversation ID from shell metadata.
Pair rejects missing or ambiguous matches. It never selects the newest session.
Pair does not start or replace a service, resume a session, or cancel a turn.

## Verify delivery

1. Confirm that the notebook footer shows OpenCode.
2. Send an error to the agent. Confirm that the same conversation receives it.
3. Wait until OpenCode is idle, then send another error. Confirm delivery again.
4. Disconnect in the footer. Confirm that OpenCode stays running.

Messages use the native prompt API with `delivery: "queue"` and follow
OpenCode's normal busy and interruption behavior.
Delivery acceptance does not prove that a model completed a response.

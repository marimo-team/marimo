# Agents

Use `mo.agents` to observe and send JSON content to agents connected with `marimo pair connect`.
Python sends and the editor's send controls use the same backend endpoints.

Messaging requires a live edit Notebook. It works in cells and Python widget callbacks, without an active cell ID.
Scripts, read-mode apps, static exports, WASM, and unrelated background threads raise `AgentContextUnavailableError`.
A live Notebook with no agents returns an empty tuple from `mo.agents.list()`.

## Observe connections

Use `subscribe_connections()` to receive immutable tuples of `AgentInfo` values.
The initial callback runs after registration returns. An empty tuple means no agents are connected.

```python
import marimo as mo

unsubscribe = mo.agents.subscribe_connections(
    lambda agents: print([(agent.id, agent.name) for agent in agents])
)
```

Callbacks run on the normal kernel loop with their owning cell context.
A busy kernel delays callbacks. Intermediate changes can coalesce into the latest state.
Callbacks do not rerun notebook cells. They must be synchronous.

Register subscriptions from a notebook cell or a synchronous widget callback with an owning cell.
Background thread registration, including `mo.Thread`, is unsupported.
Cell reruns, deletion, and runtime shutdown remove subscriptions.
Call `unsubscribe()` to remove one earlier. Repeated removal is safe.
A callback that has started can finish. Removal prevents later callbacks from starting.
Callback errors use normal runtime reporting and do not stop other subscribers.

Libraries can update an existing widget model from the callback:

```python
unsubscribe = mo.agents.subscribe_connections(
    lambda agents: widget.set_trait("agent_connected", bool(agents))
)
```

The widget owns that trait and its display policy. Its close handler can call `unsubscribe()`.
No marimo frontend import is needed. Presence indicates a live agent attachment, not native inbox readiness.
Duplicate streams with the same logical identity represent one agent. The newest remaining stream supplies its name.

## Send from a callback

Each explicit call sends a new message. A reactive rerun also sends a new message.
Use a callback to send content after a user action:

```python
import marimo as mo


def send_selection(_):
    connected = mo.agents.list()
    if len(connected) == 1:
        result = mo.agents.send(
            {"selected_rows": [1, 3, 5]},
            to=connected[0].id,
        )
        print(result.recipients)


mo.ui.button(label="Send selection to the sole agent", on_change=send_selection)
```

With several agents, let the user choose an ID from `mo.agents.list()`.
Names can be absent or repeated. IDs identify connections within this Notebook.
Pair IDs survive stream reconnects. An attachment without a logical identity uses its attachment ID, which changes on reconnect.
An absent target returns a `rejected` result. The service never substitutes another recipient.

Use `mo.agents.broadcast(message)` for an explicit broadcast.
The service selects connected recipients once, at acceptance. An empty broadcast raises `NoAgentsConnectedError`.

Messages accept JSON values: strings, arrays, objects with string keys, finite numbers, booleans, and `None`.
Messages need no required content fields. Unsupported values raise `TypeError` or `ValueError` before dispatch.

## Interpret results

`SendResult.recipients` contains one immutable result per selected agent.

| Status | Meaning |
| --- | --- |
| `submitted` | Native evidence confirms that the harness accepted the message. |
| `rejected` | Submission did not occur, or the destination definitely refused it. |
| `unknown` | The message can reach the agent without a confirmed outcome. |

`submitted` does not mean that the agent read the message or completed a task.
Codex reports successful native queue admission. OpenCode reports a validated admission response for the selected conversation.
Claude Code reports `unknown` after a completed socket write because its inbox does not confirm acceptance.
Each result can include an explanatory `detail`.

`list()`, `send()`, and `broadcast()` accept a positive, finite `timeout` in seconds, with a default of 30.
Broadcast uses one wait budget for all recipients. A timeout stops the wait and does not cancel native delivery.
If the overall response is lost after possible dispatch, sending raises `SendOutcomeUnknownError`.
A listing timeout or subscription setup failure raises `AgentError`.

The service does not retry sends automatically. After an unknown outcome, another send can duplicate the content.
Connection loss or server shutdown can also leave an outcome unknown.

::: marimo.agents.list

::: marimo.agents.subscribe_connections

::: marimo.agents.send

::: marimo.agents.broadcast

::: marimo.agents.AgentInfo

::: marimo.agents.SendResult

::: marimo.agents.RecipientResult

::: marimo.agents.AgentError

::: marimo.agents.AgentContextUnavailableError

::: marimo.agents.NoAgentsConnectedError

::: marimo.agents.SendOutcomeUnknownError

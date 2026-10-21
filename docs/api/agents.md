# Agent messaging

Use `mo.agents` to send JSON content to agents connected with `marimo pair connect`.
The Python interface and the editor's send controls use the same backend endpoints.

Messaging requires a live edit Notebook. It works in cells and Python widget callbacks, without an active cell ID.
Scripts, read-mode apps, static exports, WASM, and unrelated background threads raise `MessagingUnavailableError`.
A live Notebook with no agents returns an empty tuple from `mo.agents.list()`.

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

All calls have a positive, finite `timeout` in seconds, with a default of 30.
Broadcast uses one wait budget for all recipients. A timeout stops the wait and does not cancel native delivery.
If the overall response is lost after possible dispatch, sending raises `SendOutcomeUnknownError`.
A listing timeout raises `AgentMessagingError`.

The service does not retry sends automatically. After an unknown outcome, another send can duplicate the content.
Connection loss or server shutdown can also leave an outcome unknown.

::: marimo.agents.list

::: marimo.agents.send

::: marimo.agents.broadcast

::: marimo.agents.AgentInfo

::: marimo.agents.SendResult

::: marimo.agents.RecipientResult

::: marimo.agents.AgentMessagingError

::: marimo.agents.MessagingUnavailableError

::: marimo.agents.NoAgentsConnectedError

::: marimo.agents.SendOutcomeUnknownError

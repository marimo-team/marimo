# Agents

Use `mo.agents` to send JSON data to connected agents and respond to connection changes.
These functions work in live editor notebooks, including widget callbacks.

## Send a message

Use `list()` to find connected agents and `send()` to send data to one agent:

```python
import marimo as mo


def send_selection(_):
    agents = mo.agents.list()
    if len(agents) == 1:
        mo.agents.send({"selected_rows": [1, 3]}, to=agents[0].id)


mo.ui.button(label="Send selection", on_change=send_selection)
```

With multiple agents, let the user choose a recipient.
Use `mo.agents.broadcast(data)` to send to all connected agents.
Each call sends a new message. Use callbacks to avoid sends on cell reruns.

The recipient selects which agent receives the native submission.
Messages remain visible to clients with access to the notebook event stream, including replay.

## Observe connections

Tools can use `subscribe_connections()` to update their interface as agents connect or disconnect.
For an existing widget with an `agent_connected` trait:

```python
unsubscribe = mo.agents.subscribe_connections(
    lambda agents: widget.set_trait("agent_connected", bool(agents))
)
```

The callback receives the connected agents, or an empty tuple if none are connected.
Call `unsubscribe()` when the tool closes.
marimo also removes the subscription when its cell reruns or is deleted.

## Results

Sends return one result per recipient:

| Status | Meaning |
| --- | --- |
| `submitted` | The agent's harness accepted the message. |
| `rejected` | The message was not submitted. |
| `unknown` | Submission could not be confirmed. |

Submission does not mean the agent read the message or completed a task.
After an unknown outcome, another send can duplicate the message.

## API reference

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

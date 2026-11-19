# Send messages to agents

Use [`mo.agents`](../../api/agents.md) to send JSON data from a notebook to
an agent connected through [marimo pair](marimo_pair.md).
Agent messaging requires a live editor notebook.

## Select a recipient

`mo.agents.available()` checks whether the current process supports messaging
without a server request. It does not require a connected agent.
`mo.agents.list()` returns only agents that can receive messages.

```python
import marimo as mo

agents = mo.agents.list() if mo.agents.available() else ()
[(agent.id, agent.name) for agent in agents]
```

Each agent has an opaque ID and a display name. Names need not be unique.
IDs remain stable across stream reconnects within a Notebook.
The listing uses first connection order. A listing does not reserve a recipient.

With one connected agent, a button can send selected rows to that agent:

```python
def send_selection(_):
    agents = mo.agents.list()
    if len(agents) == 1:
        result = mo.agents.send({"selected_rows": [1, 3]}, to=agents[0].id)
        for recipient in result.recipients:
            print(recipient.name, recipient.status, recipient.reason)


send_button = mo.ui.button(label="Send selection", on_change=send_selection)
send_button
```

With multiple agents, use their IDs to select a recipient explicitly.
`send()` waits for a submission result. A disconnected recipient returns
`rejected` with `not-connected`, rather than an exception.

!!! warning "Cell reruns send again"

    Each send call creates a new Message ID. A reactive cell rerun sends again.
    Use a widget callback to send only on user interaction.

## Broadcast a message

`broadcast()` sends the same content to all agents that can receive at the
time of the call. It waits for their submission results.

```python
def notify_agents(_):
    result = mo.agents.broadcast({"note": "The data changed."}, sender="data-view")
    print(result.recipients)


broadcast_button = mo.ui.button(label="Notify all agents", on_change=notify_agents)
broadcast_button
```

An empty broadcast returns a `SendResult` with an empty `recipients` tuple.
One Message ID covers all recipients of a broadcast.

## Send without blocking

`start_send()` returns a `SendFuture` immediately. Its `message_id` is
available before the result. `start_broadcast()` is the corresponding
broadcast form.

```python
def show_result(future):
    try:
        result = future.result()
    except mo.agents.AgentError as error:
        print(error)
        return
    for recipient in result.recipients:
        print(recipient.name, recipient.status, recipient.reason)


def start_selection(_):
    agents = mo.agents.list()
    if len(agents) == 1:
        future = mo.agents.start_send({"selected_rows": [1, 3]}, to=agents[0].id)
        print(future.message_id)
        future.add_done_callback(show_result)


start_button = mo.ui.button(label="Send selection", on_change=start_selection)
start_button
```

Done callbacks run on a marimo thread. If the future is already complete,
`add_done_callback()` runs the callback on the caller's thread.
Argument and context errors raise at the call. Request errors appear through
`future.result()`.

All send forms default to a 30-second timeout. For future forms, the timeout
starts after dispatch. At most four sends run at once.
A timeout on `future.result(timeout=...)` only stops the wait.
`future.cancel()` can prevent a queued send, but cannot stop a running send.

## Read submission results

Each `SendResult` has a `message_id` and a `recipients` tuple.
Each recipient has an `agent_id`, `name`, `status`, `reason`, and optional
`detail` for people. The detail has a limit of 500 characters.

The status determines whether a second send is safe. The reason describes
the cause of the outcome.

| Status | Reason | Meaning |
| --- | --- | --- |
| `submitted` | `None` | The harness gave acceptance evidence. |
| `rejected` | `not-connected` | The recipient was not connected at the send. |
| `rejected` | `disconnected` | The connection closed before submission was possible. |
| `rejected` | `timeout` | The message did not reach submission before the deadline. |
| `rejected` | `refused` | The harness refused the message. |
| `rejected` | `invalid` | The message is not valid for the harness. |
| `unknown` | `unconfirmed` | The harness gives no acceptance evidence. |
| `unknown` | `timeout` | Submission was possible, but no result arrived before the deadline. |
| `unknown` | `disconnected` | The connection closed after submission became possible. |
| `unknown` | `failed` | An error left the submission outcome uncertain. |

After `rejected`, a second send to that recipient cannot duplicate delivery.
After `unknown`, a second send can duplicate delivery.
For a broadcast, inspect each recipient separately.

`submitted` requires acceptance evidence from the harness, the program that
owns the agent's conversation. Claude Code returns `unknown` with
`unconfirmed` because it gives no acceptance evidence.
No status proves that the agent read the message or completed a task.

Invalid arguments raise `TypeError` or `ValueError`. Operational failures
raise `mo.agents.AgentError`. A thread without a marimo context raises
`mo.agents.AgentContextUnavailableError`.
`mo.agents.SendOutcomeUnknownError` means that the overall response was lost
or invalid after possible dispatch. Another send can duplicate delivery.

## Observe connections

`subscribe_connections()` receives an immutable tuple of `AgentInfo` values
as agents connect or disconnect. An empty tuple means no agents can receive.

```python
def watch_connections():
    history = []

    def update_connections(agents):
        history.append(agents)
        print([(agent.id, agent.name) for agent in agents])

    unsubscribe = mo.agents.subscribe_connections(update_connections)
    return history, unsubscribe


connection_history, unsubscribe = watch_connections()
```

Callbacks run on the kernel queue without an owning cell. They do not rerun
cells. A busy kernel delays callbacks, and intermediate changes can be skipped.
Capture callback dependencies in a closure, as in this example.
Registration waits at most one second for the editor response.
Register from a notebook cell or widget callback, rather than a background thread.

When the consumer closes, call `unsubscribe()`.
Before you register a replacement, remove the previous subscription.
Repeated calls are safe. Cell reruns and deletion do not remove subscriptions.
Session shutdown removes subscriptions.

## Limits

- Messages accept JSON values: dictionaries with string keys, lists, strings,
  finite numbers, booleans, and `None`.
- Each message has a limit of 4 MB (4,194,304 bytes) of encoded JSON.
- The optional `sender` is an unverified label, limited to one line and 64 characters.
  It gives no authority.
- Message content does not go on the Notebook event stream.
- There is no durable queue, automatic retry, or reply channel.

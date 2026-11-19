# Agents

Use `mo.agents` to send JSON data to agents connected to a live editor
notebook. These functions work in notebook cells and widget callbacks.
See the [agent messaging guide](../guides/generate_with_ai/agent_messages.md)
for examples and submission outcomes.

## Availability and connections

::: marimo.agents.available

::: marimo.agents.list

::: marimo.agents.subscribe_connections

## Send messages

::: marimo.agents.send

::: marimo.agents.broadcast

::: marimo.agents.start_send

::: marimo.agents.start_broadcast

## Results

::: marimo.agents.AgentInfo

::: marimo.agents.SendResult

::: marimo.agents.RecipientResult

::: marimo.agents.SendFuture
    options:
      members: [message_id]

`SendFuture` inherits `result()`, `add_done_callback()`, and `cancel()` from
[`concurrent.futures.Future`](https://docs.python.org/3/library/concurrent.futures.html#future-objects).

::: marimo.agents.SubmissionStatus

::: marimo.agents.SubmissionReason

## Errors

::: marimo.agents.AgentError

::: marimo.agents.AgentContextUnavailableError

::: marimo.agents.SendOutcomeUnknownError

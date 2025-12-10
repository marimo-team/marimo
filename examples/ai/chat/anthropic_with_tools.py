# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "anthropic>=0.39.0",
# ]
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using mo.ui.chat with Anthropic Tool Calls

    This example demonstrates how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) with Anthropic Claude tool calls.

    Anthropic uses a different streaming format than OpenAI. This example shows how to manually
    convert Anthropic's event-based streaming to the AI SDK compatible format that marimo's
    chat UI expects.

    The model can use tools to:
    - Get the current weather for a location
    - Calculate mathematical expressions

    Tool calls are displayed in the chat UI with collapsible accordions showing the tool name, input, and output.
    """)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="Anthropic API key", kind="password")
    input_key if not os_key else None
    return input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your Anthropic API key in the input field or set the `ANTHROPIC_API_KEY` environment variable."),
    )
    return (key,)


@app.cell
def _():
    import json

    # Define tools in Anthropic format
    tools = [
        {
            "name": "get_weather",
            "description": "Get the current weather for a location",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The temperature unit",
                    },
                },
                "required": ["location"],
            },
        },
        {
            "name": "calculate",
            "description": "Evaluate a mathematical expression",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate, e.g. '2 + 2 * 3'",
                    },
                },
                "required": ["expression"],
            },
        },
    ]


    def execute_tool(tool_name: str, arguments: dict) -> str:
        """Execute a tool and return the result."""
        if tool_name == "get_weather":
            location = arguments.get("location", "Unknown")
            unit = arguments.get("unit", "fahrenheit")
            # Simulated weather data
            temp = 72 if unit == "fahrenheit" else 22
            return json.dumps({
                "location": location,
                "temperature": temp,
                "unit": unit,
                "conditions": "sunny",
                "humidity": "45%",
            })
        elif tool_name == "calculate":
            expression = arguments.get("expression", "0")
            try:
                # Note: In production, use a safer evaluation method
                result = eval(expression)  # noqa: S307
                return json.dumps({"expression": expression, "result": result})
            except Exception as e:
                return json.dumps({"error": str(e)})
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    return execute_tool, json, tools


@app.cell
def _(execute_tool, json, key, tools):
    import anthropic

    client = anthropic.Anthropic(api_key=key)


    def chat_with_tools(messages, config):
        """
        A chat model that supports Anthropic tool calls with streaming.

        This function manually converts Anthropic's event-based streaming format
        to the AI SDK compatible format that marimo's chat UI expects.

        Anthropic streaming events:
        - content_block_start: Start of a text or tool_use block
        - content_block_delta: Delta for text or tool input
        - content_block_stop: End of a content block
        - message_stop: End of message
        """
        # Convert marimo ChatMessages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg.role == "user":
                anthropic_messages.append({"role": "user", "content": str(msg.content)})
            elif msg.role == "assistant":
                # Check if this message has tool call parts
                if msg.parts:
                    content_blocks = []
                    tool_results = []

                    for part in msg.parts:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                content_blocks.append({
                                    "type": "text",
                                    "text": part.get("text", ""),
                                })
                            elif part.get("type", "").startswith("tool-"):
                                tool_name = part["type"].replace("tool-", "")
                                tool_call_id = part.get("toolCallId") or part.get("tool_call_id", "")
                                # Add tool_use block to assistant message
                                content_blocks.append({
                                    "type": "tool_use",
                                    "id": tool_call_id,
                                    "name": tool_name,
                                    "input": part.get("input", {}),
                                })
                                # Collect tool result for user message
                                if part.get("output") is not None:
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": tool_call_id,
                                        "content": json.dumps(part["output"]) if isinstance(part["output"], dict) else str(part["output"]),
                                    })

                    if content_blocks:
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": content_blocks,
                        })
                    if tool_results:
                        anthropic_messages.append({
                            "role": "user",
                            "content": tool_results,
                        })
                else:
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": str(msg.content),
                    })

        # Call Anthropic with streaming
        with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=config.max_tokens or 1024,
            messages=anthropic_messages,
            tools=tools,
            system="You are a helpful assistant. Use the provided tools when appropriate to help answer questions.",
        ) as stream:
            # Track state for converting Anthropic events to AI SDK format
            parts = []
            current_text = ""
            current_tool_use = None
            tool_input_json = ""

            for event in stream:
                event_type = event.type

                if event_type == "content_block_start":
                    block = event.content_block
                    if block.type == "text":
                        # Text block starting
                        current_text = ""
                    elif block.type == "tool_use":
                        # Tool use block starting
                        current_tool_use = {
                            "id": block.id,
                            "name": block.name,
                        }
                        tool_input_json = ""

                elif event_type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        # Accumulate text
                        current_text += delta.text
                        # Yield text update
                        yield current_text

                    elif delta.type == "input_json_delta":
                        # Accumulate tool input JSON
                        tool_input_json += delta.partial_json

                elif event_type == "content_block_stop":
                    # Content block finished
                    if current_text:
                        # Add completed text part
                        # Check if we already have a text part to update
                        text_part_exists = False
                        for i, p in enumerate(parts):
                            if p.get("type") == "text":
                                parts[i]["text"] = current_text
                                text_part_exists = True
                                break
                        if not text_part_exists:
                            parts.append({"type": "text", "text": current_text})

                    if current_tool_use:
                        # Parse the accumulated JSON input
                        try:
                            tool_input = json.loads(tool_input_json) if tool_input_json else {}
                        except json.JSONDecodeError:
                            tool_input = {}

                        tool_name = current_tool_use["name"]
                        tool_call_id = current_tool_use["id"]

                        # Add tool part in "input-available" state
                        parts.append({
                            "type": f"tool-{tool_name}",
                            "toolCallId": tool_call_id,
                            "state": "input-available",
                            "input": tool_input,
                        })
                        yield {"parts": parts.copy()}

                        # Execute the tool
                        result = execute_tool(tool_name, tool_input)

                        # Update to "output-available" state
                        parts[-1]["state"] = "output-available"
                        try:
                            parts[-1]["output"] = json.loads(result)
                        except json.JSONDecodeError:
                            parts[-1]["output"] = result
                        yield {"parts": parts.copy()}

                        # Reset tool state
                        current_tool_use = None
                        tool_input_json = ""

                elif event_type == "message_stop":
                    # Message complete
                    pass

        # After streaming completes, check if we need to get a final response
        # (if there were tool calls, we need to send results back)
        tool_parts = [p for p in parts if p.get("type", "").startswith("tool-")]

        if tool_parts:
            # Build messages with tool results for final response
            final_messages = anthropic_messages.copy()

            # Add assistant message with tool uses
            assistant_content = []
            if current_text:
                assistant_content.append({"type": "text", "text": current_text})

            for part in tool_parts:
                tool_name = part["type"].replace("tool-", "")
                assistant_content.append({
                    "type": "tool_use",
                    "id": part["toolCallId"],
                    "name": tool_name,
                    "input": part["input"],
                })

            final_messages.append({
                "role": "assistant",
                "content": assistant_content,
            })

            # Add tool results as user message
            tool_results = []
            for part in tool_parts:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": part["toolCallId"],
                    "content": json.dumps(part["output"]) if isinstance(part.get("output"), dict) else str(part.get("output", "")),
                })

            final_messages.append({
                "role": "user",
                "content": tool_results,
            })

            # Get final response
            with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=config.max_tokens or 1024,
                messages=final_messages,
                system="You are a helpful assistant. Use the provided tools when appropriate to help answer questions.",
            ) as final_stream:
                final_text = ""
                for event in final_stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        final_text += event.delta.text

                        # Update or add text part at the end
                        text_part_idx = None
                        for i, p in enumerate(parts):
                            if p.get("type") == "text" and i == len(parts) - 1:
                                text_part_idx = i
                                break

                        if text_part_idx is not None:
                            parts[text_part_idx]["text"] = final_text
                        else:
                            parts.append({"type": "text", "text": final_text})

                        yield {"parts": parts.copy()}

            # Final yield
            yield {"parts": parts}

        elif parts:
            # No tool calls, just yield final parts
            yield {"parts": parts}

    return chat_with_tools, client, anthropic


@app.cell
def _(chat_with_tools, mo):
    chatbot = mo.ui.chat(
        chat_with_tools,
        prompts=[
            "What's the weather like in San Francisco?",
            "Calculate 15% tip on a $85 bill",
            "What's the weather in Tokyo in celsius?",
        ],
        show_configuration_controls=True,
    )
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Anthropic Streaming Format

    Anthropic uses an event-based streaming format that differs from OpenAI:

    | Event Type | Description |
    |------------|-------------|
    | `content_block_start` | Start of a text or tool_use block |
    | `content_block_delta` | Delta for text (`text_delta`) or tool input (`input_json_delta`) |
    | `content_block_stop` | End of a content block |
    | `message_stop` | End of message |

    ### Converting to AI SDK Format

    This example manually converts Anthropic's events to the AI SDK compatible format:

    ```python
    # Anthropic tool_use block:
    {
        "type": "tool_use",
        "id": "toolu_abc123",
        "name": "get_weather",
        "input": {"location": "San Francisco"}
    }

    # Converted to AI SDK format:
    {
        "type": "tool-get_weather",
        "toolCallId": "toolu_abc123",
        "state": "input-available",  # or "output-available"
        "input": {"location": "San Francisco"},
        "output": {...}  # when state is "output-available"
    }
    ```

    The key differences:
    - Tool type is prefixed with `tool-` (e.g., `tool-get_weather`)
    - Uses `toolCallId` (camelCase) instead of `id`
    - Adds `state` field to track tool execution progress
    """)
    return


@app.cell
def _(chatbot):
    # Access the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()

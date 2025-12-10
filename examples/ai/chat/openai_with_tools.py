# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "openai>=1.0.0",
# ]
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using mo.ui.chat with Tool Calls

    This example demonstrates how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) with OpenAI-compatible tool calls.

    **Works with any OpenAI-compatible provider:**
    - OpenAI (default)
    - DeepSeek (`base_url="https://api.deepseek.com"`)
    - Groq (`base_url="https://api.groq.com/openai/v1"`)
    - Together AI (`base_url="https://api.together.xyz/v1"`)
    - Any other OpenAI-compatible API

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

    # Provider configuration - change these to use a different OpenAI-compatible provider
    PROVIDER_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)  # e.g., "https://api.deepseek.com"
    PROVIDER_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1")  # e.g., "deepseek-chat"

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="API key", kind="password")
    input_key if not os_key else None
    return PROVIDER_BASE_URL, PROVIDER_MODEL, input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your OpenAI API key in the input field or set the `OPENAI_API_KEY` environment variable."),
    )
    return (key,)


@app.cell
def _():
    import json

    # Define the tools that the model can use
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a location",
                "parameters": {
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
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a mathematical expression",
                "parameters": {
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
def _(PROVIDER_BASE_URL, PROVIDER_MODEL, execute_tool, json, key, tools):
    import openai
    import uuid
    from typing import Any

    # Create client - works with any OpenAI-compatible API
    client = openai.OpenAI(
        api_key=key,
        base_url=PROVIDER_BASE_URL,  # None uses default OpenAI URL
    )


    def chat_with_tools(messages, config):
        """
        A chat model that supports tool calls with streaming.

        This function:
        1. Sends messages to OpenAI with tool definitions
        2. If the model requests tool calls, executes them
        3. Streams the response with tool call status updates
        4. Yields structured parts for the UI to display
        """
        # Convert marimo ChatMessages to OpenAI format
        openai_messages = []
        for msg in messages:
            if msg.role == "system":
                openai_messages.append({"role": "system", "content": str(msg.content)})
            elif msg.role == "user":
                openai_messages.append({"role": "user", "content": str(msg.content)})
            elif msg.role == "assistant":
                # Check if this message has tool call parts
                if msg.parts:
                    for part in msg.parts:
                        if isinstance(part, dict) and part.get("type", "").startswith("tool-"):
                            # Add assistant message with tool_calls
                            tool_name = part["type"].replace("tool-", "")
                            tool_call_id = part.get("toolCallId") or part.get("tool_call_id", "")
                            openai_messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(part["input"]),
                                    },
                                }],
                            })
                            # Add tool result
                            openai_messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(part["output"]) if part.get("output") else "",
                            })
                        elif isinstance(part, dict) and part.get("type") == "text":
                            openai_messages.append({
                                "role": "assistant",
                                "content": part.get("text", ""),
                            })
                else:
                    openai_messages.append({"role": "assistant", "content": str(msg.content)})

        # Add system message if not present
        if not any(m.get("role") == "system" for m in openai_messages):
            openai_messages.insert(0, {
                "role": "system",
                "content": "You are a helpful assistant. Use the provided tools when appropriate to help answer questions.",
            })

        # Call OpenAI-compatible API with tools
        response = client.chat.completions.create(
            model=PROVIDER_MODEL,
            messages=openai_messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=config.max_tokens or 1024,
            temperature=config.temperature or 0.7,
            stream=True,
        )

        # Process the streaming response following OpenAI's format:
        # - delta.content: string text (or None)
        # - delta.tool_calls: list of tool call chunks with index, id, function.name, function.arguments
        #
        # We yield:
        # - Strings for text content (marimo accumulates these)
        # - {"parts": [...]} dicts for structured responses with tool calls

        collected_tool_calls = {}  # index -> {id, name, arguments}
        text_content = ""

        for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue

            delta = choice.delta

            # 1) Handle text content - delta.content is a string (or None)
            if delta.content:
                text_content += delta.content
                # Yield delta (new content only) - marimo accumulates it
                yield delta.content

            # 2) Handle tool calls - delta.tool_calls is a list of partial updates
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index  # Stable index for this tool call

                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": None,
                            "name": None,
                            "arguments": "",
                        }

                    entry = collected_tool_calls[idx]

                    # id usually only appears on first chunk
                    if tc.id:
                        entry["id"] = tc.id

                    if tc.function:
                        if tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function.arguments:
                            # arguments stream as JSON string fragments - concatenate
                            entry["arguments"] += tc.function.arguments

            # 3) Check finish_reason
            if choice.finish_reason:
                break

        # After streaming: if we have tool calls, execute them and yield structured response
        if collected_tool_calls:
            # Build parts array following AI SDK / Vercel format:
            # - Text parts: {"type": "text", "text": "..."}
            # - Tool parts: {"type": "tool-{name}", "toolCallId": "...", "state": "...", "input": {...}, "output": {...}}
            parts: list[dict[str, Any]] = []

            # Add any text content first
            if text_content:
                parts.append({"type": "text", "text": text_content})

            # Process each tool call by index
            for idx in sorted(collected_tool_calls.keys()):
                entry = collected_tool_calls[idx]
                tool_call_id = entry["id"] or f"call_{uuid.uuid4().hex[:8]}"
                tool_name = entry["name"] or "unknown"

                # Parse the accumulated arguments JSON
                try:
                    arguments = json.loads(entry["arguments"]) if entry["arguments"] else {}
                except json.JSONDecodeError:
                    arguments = {}

                # Create tool part in "input-available" state (AI SDK compatible)
                tool_part: dict[str, Any] = {
                    "type": f"tool-{tool_name}",
                    "toolCallId": tool_call_id,  # camelCase for AI SDK
                    "state": "input-available",
                    "input": arguments,
                }
                parts.append(tool_part)

                # Yield parts with tool in "input-available" state
                # This dict MUST have "parts" key for marimo to detect it
                yield {"parts": [p.copy() if isinstance(p, dict) else p for p in parts]}

                # Execute the tool
                result = execute_tool(tool_name, arguments)

                # Update to "output-available" state with result
                tool_part["state"] = "output-available"
                try:
                    tool_part["output"] = json.loads(result)
                except json.JSONDecodeError:
                    tool_part["output"] = result

                # Yield parts with tool in "output-available" state
                yield {"parts": [p.copy() if isinstance(p, dict) else p for p in parts]}

            # Now call the model again with tool results to get final response
            # Build messages with tool results
            final_messages = openai_messages.copy()

            # Add assistant message with tool calls
            tool_calls_for_message = []
            for idx in sorted(collected_tool_calls.keys()):
                tool_call_data = collected_tool_calls[idx]
                tool_calls_for_message.append({
                    "id": tool_call_data["id"] or f"call_{uuid.uuid4().hex[:8]}",
                    "type": "function",
                    "function": {
                        "name": tool_call_data["name"],
                        "arguments": tool_call_data["arguments"],
                    },
                })

            final_messages.append({
                "role": "assistant",
                "content": text_content if text_content else None,
                "tool_calls": tool_calls_for_message,
            })

            # Add tool results
            for idx in sorted(collected_tool_calls.keys()):
                tool_call_data = collected_tool_calls[idx]
                tool_call_id = tool_call_data["id"] or f"call_{uuid.uuid4().hex[:8]}"
                tool_name = tool_call_data["name"]

                try:
                    arguments = json.loads(tool_call_data["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                result = execute_tool(tool_name, arguments)
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result,
                })

            # Get final response
            final_response = client.chat.completions.create(
                model=PROVIDER_MODEL,
                messages=final_messages,
                max_tokens=config.max_tokens or 1024,
                temperature=config.temperature or 0.7,
                stream=True,
            )

            # Stream the final response text as deltas
            # We need to yield the full parts array to preserve tool parts
            # but also stream text updates
            final_text = ""

            # Add text part placeholder at the end for streaming
            text_part: dict[str, Any] = {"type": "text", "text": ""}
            parts.append(text_part)

            for chunk in final_response:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue

                delta = choice.delta
                if delta.content:
                    final_text += delta.content
                    # Update the text part in place
                    text_part["text"] = final_text

                    # Yield the full parts array (preserves tool parts + updated text)
                    yield {"parts": [p.copy() if isinstance(p, dict) else p for p in parts]}

                if choice.finish_reason:
                    break

            # Final yield with complete response
            yield {"parts": [p.copy() if isinstance(p, dict) else p for p in parts]}

        # If no tool calls, text was already streamed as deltas during the loop
        # No additional yield needed - marimo accumulated the deltas

    return chat_with_tools, client, openai, uuid


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
    ## How it works

    The `chat_with_tools` function:

    1. **Converts messages** to OpenAI format, including any previous tool calls from the chat history
    2. **Streams the response** from the API, collecting any tool calls
    3. **Yields structured parts** that the UI can display:
       - Text parts for regular content
       - Tool parts with `state: "input-available"` when a tool is being invoked
       - Tool parts with `state: "output-available"` after execution
    4. **Executes tools** and sends results back to the model for a final response

    ### Tool Part Format (AI SDK Compatible)

    ```python
    {
        "type": "tool-{tool_name}",  # e.g., "tool-get_weather"
        "toolCallId": "call_abc123",  # Unique ID for the tool call
        "state": "input-available",   # or "output-available"
        "input": {"arg": "value"},    # Tool input arguments
        "output": {"result": "..."},  # Tool output (when state is "output-available")
    }
    ```

    ### Using with Other Providers

    Set environment variables to use a different OpenAI-compatible provider:

    ```bash
    # DeepSeek
    export OPENAI_API_KEY="your-deepseek-key"
    export OPENAI_BASE_URL="https://api.deepseek.com"
    export OPENAI_MODEL="deepseek-chat"

    # Groq
    export OPENAI_API_KEY="your-groq-key"
    export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
    export OPENAI_MODEL="llama-3.1-70b-versatile"
    ```
    """)
    return


@app.cell
def _(chatbot):
    # Access the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "pydantic-ai",
# ]
# ///

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using Pydantic AI with Tool Calls

    This example demonstrates how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) with [Pydantic AI](https://ai.pydantic.dev/) for **dramatically simplified tool handling**.

    **Compare this to `openai_with_tools.py`** - all the tool call boilerplate is gone!

    **Works with any Pydantic AI provider:**
    - OpenAI: `"openai:gpt-4.1"`, `"openai:gpt-4o"`
    - Anthropic: `"anthropic:claude-sonnet-4-5"`
    - Google: `"google-gla:gemini-2.0-flash"`
    - Groq: `"groq:llama-3.3-70b-versatile"`
    - And many more...

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

    # Provider configuration - model in "provider:model-name" format
    PROVIDER_MODEL = os.environ.get("PYDANTIC_AI_MODEL", "openai:gpt-4.1")

    os_key = os.environ.get("OPENAI_API_KEY")
    input_key = mo.ui.text(label="API key", kind="password")
    input_key if not os_key else None
    return PROVIDER_MODEL, input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your API key in the input field or set the appropriate environment variable (e.g., `OPENAI_API_KEY`)."),
    )
    return (key,)


@app.cell
def _():
    # Define tools as simple functions with docstrings
    # Pydantic AI extracts the schema automatically from type hints and docstrings

    def get_weather(location: str, unit: str = "fahrenheit") -> dict:
        """Get the current weather for a location.

        Args:
            location: The city and state, e.g. "San Francisco, CA"
            unit: Temperature unit, either "celsius" or "fahrenheit"
        """
        # Simulated weather data
        temp = 72 if unit == "fahrenheit" else 22
        return {
            "location": location,
            "temperature": temp,
            "unit": unit,
            "conditions": "sunny",
            "humidity": "45%",
        }

    def calculate(expression: str) -> dict:
        """Evaluate a mathematical expression.

        Args:
            expression: The math expression to evaluate, e.g. "2 + 2 * 3"
        """
        try:
            # Note: In production, use a safer evaluation method
            result = eval(expression)  # noqa: S307
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"error": str(e)}

    return calculate, get_weather


@app.cell
def _(PROVIDER_MODEL, calculate, get_weather, key, mo):
    # That's it! Just pass the tools and model to mo.ai.llm.pydantic_ai
    # No need to handle:
    # - Message conversion
    # - Streaming
    # - Tool call parsing
    # - Tool execution loop
    # - Final response generation

    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(
            PROVIDER_MODEL,
            tools=[get_weather, calculate],
            system_message="You are a helpful assistant. Use the provided tools when appropriate to help answer questions.",
            api_key=key,
        ),
        prompts=[
            "What's the weather like in San Francisco?",
            "Calculate 15% tip on a $85 bill",
            "What's the weather in Tokyo in celsius?",
        ]
    )
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How it works

    The `mo.ai.llm.pydantic_ai` class handles everything automatically:

    1. **Tool registration** - Functions are converted to tool schemas via Pydantic AI
    2. **Streaming** - Text is streamed as it's generated
    3. **Tool execution** - When the model calls a tool, it's executed and results sent back
    4. **Structured parts** - Tool calls are yielded as structured parts for the UI to display
    5. **Multi-provider support** - Works with any Pydantic AI supported provider

    ### Defining Tools

    Tools are just Python functions with type hints and docstrings:

    ```python
    def get_weather(location: str, unit: str = "fahrenheit") -> dict:
        '''Get the current weather for a location.

        Args:
            location: The city and state, e.g. "San Francisco, CA"
            unit: Temperature unit, either "celsius" or "fahrenheit"
        '''
        return {"location": location, "temperature": 72}
    ```

    Pydantic AI extracts:
    - Function name → tool name
    - Docstring → tool description
    - Type hints → parameter schema
    - Args section → parameter descriptions

    ### Using Different Providers

    Set the `PYDANTIC_AI_MODEL` environment variable or change the model string:

    ```bash
    # OpenAI
    export PYDANTIC_AI_MODEL="openai:gpt-4.1"
    export OPENAI_API_KEY="your-key"

    # Anthropic
    export PYDANTIC_AI_MODEL="anthropic:claude-sonnet-4-5"
    export ANTHROPIC_API_KEY="your-key"

    # Google
    export PYDANTIC_AI_MODEL="google-gla:gemini-2.0-flash"
    export GOOGLE_API_KEY="your-key"

    # Groq
    export PYDANTIC_AI_MODEL="groq:llama-3.3-70b-versatile"
    export GROQ_API_KEY="your-key"
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

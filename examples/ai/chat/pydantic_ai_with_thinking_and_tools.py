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
    # Using Pydantic AI with Thinking and Tools

    This example demonstrates how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) with [Pydantic AI](https://ai.pydantic.dev/) featuring both **thinking/reasoning** and **tool calls**.

    When enabled, you'll see:
    - **Thinking accordion** - The model's reasoning process displayed before the response
    - **Tool call accordions** - Tool invocations with inputs and outputs

    This is especially powerful for complex tasks where you want transparency into:
    - How the model is reasoning about the problem
    - What tools it decides to use and why
    - The step-by-step execution flow

    **Supported providers:**
    - Anthropic: `"anthropic:claude-sonnet-4-5"` (recommended for thinking)
    - OpenAI: `"openai:gpt-4.1"`
    - Google: `"google-gla:gemini-2.5-pro"`
    - Groq: `"groq:qwen-qwq-32b"`
    """)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    import os

    # Use Anthropic's Claude for best thinking support
    PROVIDER_MODEL = os.environ.get(
        "PYDANTIC_AI_MODEL", "anthropic:claude-sonnet-4-5"
    )

    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="API key", kind="password")
    input_key if not os_key else None
    return PROVIDER_MODEL, input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md(
            "Please provide your API key in the input field or set the "
            "appropriate environment variable (e.g., `ANTHROPIC_API_KEY`)."
        ),
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
    # Combine thinking AND tools for maximum transparency
    # The model will show its reasoning, then use tools as needed

    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(
            PROVIDER_MODEL,
            tools=[get_weather, calculate],
            enable_thinking=True,  # Enable thinking/reasoning
            system_message=(
                "You are a helpful assistant. Think step-by-step when solving "
                "problems. Use the provided tools when appropriate."
            ),
            api_key=key,
        ),
        prompts=[
            "What's the weather in San Francisco and Tokyo? Compare them.",
            "If the temperature in SF is 72°F, what is it in Celsius? Then calculate 15% tip on a $85 dinner bill.",
            "I have 3 red balls and 2 blue balls. What's the probability of picking 2 red balls in a row without replacement?",
        ],
    )
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How it works

    With both `enable_thinking=True` and `tools=[...]`:

    1. **Thinking first** - The model's reasoning appears in a collapsible accordion
    2. **Tool calls** - When the model uses tools, each call appears in its own accordion
    3. **Final response** - The synthesized answer based on thinking and tool results

    ### Example Flow

    For a query like "What's the weather in SF and Tokyo? Compare them.":

    1. 🧠 **Thinking**: "I need to get weather for both cities, then compare..."
    2. 🔧 **Tool: get_weather** → SF: 72°F, sunny
    3. 🔧 **Tool: get_weather** → Tokyo: 22°C, sunny
    4. 💬 **Response**: "San Francisco is 72°F (22°C) and Tokyo is 22°C. Both are sunny..."

    ### Configuration Options

    ```python
    # Basic: enable with defaults
    enable_thinking=True

    # Anthropic: control thinking budget
    enable_thinking={"budget_tokens": 2048}

    # OpenAI: control reasoning effort
    enable_thinking={"effort": "high", "summary": "detailed"}

    # Google: include thoughts
    enable_thinking={"include_thoughts": True}
    ```

    See https://ai.pydantic.dev/thinking/ for provider-specific details.
    """)
    return


@app.cell
def _(chatbot):
    # Access the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()


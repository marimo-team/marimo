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
    import os

    return mo, os


@app.cell
def _(mo, os):
    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="Anthropic API key", kind="password")
    input_key if not os_key else None
    return input_key, os_key


@app.cell
def _(input_key, mo, os, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md(
            "Please provide your Anthropic API key in the input field or set "
            "`ANTHROPIC_API_KEY` environment variable."
        ),
    )

    # Set the API key for pydantic-ai to use
    os.environ["ANTHROPIC_API_KEY"] = key
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
def _(calculate, get_weather, mo):
    # Import Pydantic AI components
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModelSettings

    # Create a Pydantic AI Agent with tools and thinking enabled
    agent = Agent(
        "anthropic:claude-sonnet-4-5",
        tools=[get_weather, calculate],
        instructions=(
            "You are a helpful assistant. Think step-by-step when solving "
            "problems. Use the provided tools when appropriate."
        ),
        # Enable thinking with Anthropic-specific settings
        model_settings=AnthropicModelSettings(
            max_tokens=8000,
            anthropic_thinking={
                "type": "enabled",
                "budget_tokens": 4000,
            },
        ),
    )

    # Pass the agent to mo.ai.llm.pydantic_ai
    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(agent),
        prompts=[
            "What's the weather in San Francisco and Tokyo? Compare them.",
            "If the temperature in SF is 72°F, what is it in Celsius? "
            "Then calculate 15% tip on a $85 dinner bill.",
            "I have 3 red balls and 2 blue balls. What's the probability of "
            "picking 2 red balls in a row without replacement?",
        ],
    )
    chatbot
    return Agent, AnthropicModelSettings, agent, chatbot


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How it works

    With `model_settings` configured for thinking and `tools` provided:

    1. **Thinking first** - The model's reasoning appears in a collapsible accordion
    2. **Tool calls** - When the model uses tools, each call appears in its own accordion
    3. **Final response** - The synthesized answer based on thinking and tool results

    ### Example Flow

    For a query like "What's the weather in SF and Tokyo? Compare them.":

    1. 🧠 **Thinking**: "I need to get weather for both cities, then compare..."
    2. 🔧 **Tool: get_weather** → SF: 72°F, sunny
    3. 🔧 **Tool: get_weather** → Tokyo: 22°C, sunny
    4. 💬 **Response**: "San Francisco is 72°F (22°C) and Tokyo is 22°C. Both are sunny..."

    ### Usage

    Create a Pydantic AI Agent and pass it to `mo.ai.llm.pydantic_ai()`:

    ```python
    from pydantic_ai import Agent
    from pydantic_ai.models.anthropic import AnthropicModelSettings

    # Create your agent with all configuration
    agent = Agent(
        "anthropic:claude-sonnet-4-5",
        tools=[get_weather, calculate],
        instructions="You are a helpful assistant.",
        model_settings=AnthropicModelSettings(
            max_tokens=8000,
            anthropic_thinking={"type": "enabled", "budget_tokens": 4000},
        ),
    )

    # Pass it to marimo
    chat = mo.ui.chat(mo.ai.llm.pydantic_ai(agent))
    ```

    The Agent API gives you full control over:
    - `tools` - Functions the model can call
    - `instructions` - System prompt
    - `model_settings` - Provider-specific settings (thinking, max_tokens, etc.)
    - `deps_type` - Dependency injection for tools
    - `output_type` - Structured output schema
    - And more - see https://ai.pydantic.dev/agents/
    """)
    return


@app.cell
def _(chatbot):
    # Access the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()

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
    # Using Pydantic AI with Thinking/Reasoning

    This example demonstrates how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) with [Pydantic AI](https://ai.pydantic.dev/) and **thinking/reasoning enabled**.

    When thinking is enabled, the model will show its reasoning process in a collapsible accordion before providing the final answer. This is especially useful for:
    - Complex problem solving
    - Multi-step reasoning
    - Debugging AI responses
    - Understanding how the model arrived at its answer

    **Supported providers for thinking:**
    - Anthropic: `"anthropic:claude-sonnet-4-5"` (recommended)
    - OpenAI: `"openai:gpt-4.1"` (with Responses API)
    - Google: `"google-gla:gemini-2.5-pro"`
    - Groq: `"groq:qwen-qwq-32b"`

    See https://ai.pydantic.dev/thinking/ for more details.
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
    PROVIDER_MODEL = os.environ.get("PYDANTIC_AI_MODEL", "anthropic:claude-sonnet-4-5")

    os_key = os.environ.get("ANTHROPIC_API_KEY")
    input_key = mo.ui.text(label="API key", kind="password")
    input_key if not os_key else None
    return PROVIDER_MODEL, input_key, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md("Please provide your API key in the input field or set the appropriate environment variable (e.g., `ANTHROPIC_API_KEY`)."),
    )
    return (key,)


@app.cell
def _(PROVIDER_MODEL, key, mo):
    # Enable thinking with default settings
    # The model will show its reasoning process in a collapsible accordion

    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(
            PROVIDER_MODEL,
            enable_thinking=True,  # Enable thinking with defaults
            system_message="You are a helpful assistant. Think step-by-step when solving problems.",
            api_key=key,
        ),
        prompts=[
            "What is 15% of 847?",
            "If I have 3 red balls and 2 blue balls, what's the probability of picking 2 red balls in a row without replacement?",
            "Explain why the sky is blue in simple terms",
        ]
    )
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How thinking works

    When `enable_thinking=True`:

    1. **Thinking accordion** - The model's reasoning process is captured and displayed in a collapsible accordion
    2. **Final answer** - After thinking, the model provides its final response
    3. **Full transparency** - You can expand the accordion to see exactly how the model arrived at its answer

    ### Customizing thinking settings

    You can pass provider-specific settings:

    ```python
    # Anthropic - control the thinking budget
    mo.ai.llm.pydantic_ai(
        "anthropic:claude-sonnet-4-5",
        enable_thinking={"budget_tokens": 2048},
    )

    # OpenAI - control reasoning effort
    mo.ai.llm.pydantic_ai(
        "openai:gpt-4.1",
        enable_thinking={"effort": "high", "summary": "detailed"},
    )

    # Google - enable thoughts in response
    mo.ai.llm.pydantic_ai(
        "google-gla:gemini-2.5-pro",
        enable_thinking={"include_thoughts": True},
    )

    # Groq - control reasoning format
    mo.ai.llm.pydantic_ai(
        "groq:qwen-qwq-32b",
        enable_thinking={"format": "parsed"},
    )
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

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


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using W&B Inference

    This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html) with [W&B Inference](https://docs.wandb.ai/inference), which provides access to open-source foundation models through an OpenAI-compatible API.

    W&B Inference offers several reasoning models that include thinking/reasoning in their responses:
    - `deepseek-ai/DeepSeek-R1-0528` - Optimized for precise reasoning tasks
    - `openai/gpt-oss-20b` - Lower latency MoE model with reasoning
    - `Qwen/Qwen3-235B-A22B-Thinking-2507` - High-performance reasoning model

    See [Available Models](https://docs.wandb.ai/inference/models) for the full list.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        <a href="https://docs.wandb.ai/inference" target="_blank" rel="noopener noreferrer">
          <img
            src="https://raw.githubusercontent.com/wandb/wandb/main/.github/wb-logo-lightbg.png"
            alt="Weights & Biases"
            width="300"
          />
        </a>
        """
    ).center()
    return


@app.cell
def _(mo):
    import os

    os_key = os.environ.get("WANDB_API_KEY")
    input_key = mo.ui.text(label="W&B API key", kind="password")
    input_key if not os_key else None
    return input_key, os, os_key


@app.cell
def _(input_key, mo, os_key):
    key = os_key or input_key.value

    mo.stop(
        not key,
        mo.md(
            "Please provide your W&B API key. "
            "Get one at [wandb.ai/authorize](https://wandb.ai/authorize)"
        ),
    )
    return (key,)


@app.cell
def _(mo):
    # Model selection - reasoning models will show thinking in the UI
    model_dropdown = mo.ui.dropdown(
        options={
            "DeepSeek R1 (Reasoning)": "deepseek-ai/DeepSeek-R1-0528",
            "OpenAI GPT OSS 20B (Reasoning)": "openai/gpt-oss-20b",
            "Qwen3 235B Thinking": "Qwen/Qwen3-235B-A22B-Thinking-2507",
            "Llama 3.3 70B": "meta-llama/Llama-3.3-70B-Instruct",
            "Llama 3.1 8B (Fast)": "meta-llama/Llama-3.1-8B-Instruct",
        },
        value="DeepSeek R1 (Reasoning)",
        label="Select Model",
    )
    model_dropdown
    return (model_dropdown,)


@app.cell
def _(key, model_dropdown):
    # For W&B Inference (and other OpenAI-compatible endpoints), we need to
    # configure a custom model with the provider and profile settings.
    # This is necessary because W&B uses a custom base_url and returns
    # reasoning in the "reasoning_content" field.

    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.profiles.openai import OpenAIModelProfile
    from pydantic_ai.providers.openai import OpenAIProvider

    # Configure the model with W&B Inference endpoint
    wandb_model = OpenAIChatModel(
        model_name=model_dropdown.value,
        provider=OpenAIProvider(
            api_key=key,
            base_url="https://api.inference.wandb.ai/v1",
        ),
        # Tell pydantic-ai where to find reasoning content
        profile=OpenAIModelProfile(
            openai_chat_thinking_field="reasoning_content",
        ),
    )

    # Create a Pydantic AI Agent with the model
    agent = Agent(
        wandb_model,
        instructions="You are a helpful assistant. Think step-by-step.",
    )
    return Agent, OpenAIChatModel, OpenAIModelProfile, OpenAIProvider, agent, wandb_model


@app.cell
def _(agent, mo):
    # Create the chat UI - pass the Agent directly
    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(agent),
        prompts=[
            "What is 15% of 85?",
            "Explain the difference between a list and a tuple in Python.",
            "If I have 3 red balls and 2 blue balls, what's the probability "
            "of picking 2 red balls in a row without replacement?",
        ],
    )
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## How it works

    When using a reasoning model, the model's reasoning process is displayed in a collapsible accordion above the response.

    ### Configuration for W&B Inference

    W&B Inference requires a custom model configuration because:
    1. It uses a custom `base_url` (not the standard OpenAI endpoint)
    2. Reasoning models return thinking in the `reasoning_content` field

    ```python
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.profiles.openai import OpenAIModelProfile

    # Configure the model
    model = OpenAIChatModel(
        model_name="deepseek-ai/DeepSeek-R1-0528",
        provider=OpenAIProvider(
            api_key="your-key",
            base_url="https://api.inference.wandb.ai/v1",
        ),
        profile=OpenAIModelProfile(
            openai_chat_thinking_field="reasoning_content",
        ),
    )

    # Create an Agent with the model
    agent = Agent(model, instructions="Think step-by-step.")

    # Use with marimo
    chat = mo.ui.chat(mo.ai.llm.pydantic_ai(agent))
    ```

    ### Standard Providers

    For standard providers like OpenAI, Anthropic, Google:

    ```python
    from pydantic_ai import Agent

    agent = Agent(
        "openai:gpt-4.1",
        tools=[my_tool],
        instructions="You are helpful.",
    )

    chat = mo.ui.chat(mo.ai.llm.pydantic_ai(agent))
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

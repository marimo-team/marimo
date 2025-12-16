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
def _(key, mo, model_dropdown):
    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(
            f"openai:{model_dropdown.value}",
            base_url="https://api.inference.wandb.ai/v1",
            api_key=key,
            enable_thinking=True,  # Show reasoning in the UI
            system_message="You are a helpful assistant. Think step-by-step.",
        ),
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

    When using a reasoning model with `enable_thinking=True`, the model's reasoning process is displayed in a collapsible accordion above the response.

    ### Reasoning Models

    Models like DeepSeek R1 and OpenAI GPT OSS include their reasoning steps in the response via the `reasoning_content` field. The `pydantic_ai` model automatically extracts and displays this.

    ### Non-reasoning Models

    For models like Llama that don't include structured reasoning, you'll just see the regular response without a thinking section.

    ### Configuration

    ```python
    mo.ai.llm.pydantic_ai(
        "openai:model-name",           # Use openai: prefix for W&B models
        base_url="https://api.inference.wandb.ai/v1",
        api_key="your-api-key",
        enable_thinking=True,          # Extract reasoning_content
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

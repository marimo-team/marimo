# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "mlx-lm==0.19.0",
#     "huggingface-hub==0.25.1",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    from mlx_lm import load, generate
    from pathlib import Path
    import marimo as mo
    from huggingface_hub import snapshot_download

    return Path, generate, load, mo, snapshot_download


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using MLX with Marimo

    ## Chat Example
    This example shows how to use [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to make a chatbot backed by Apple's MLX, using the `mlx_lm` library and marimo.
    [`mlx_lm`](https://github.com/ml-explore/mlx-examples/tree/main/llm) is a library for running large language models on Apple Silicon.
    [`mlx`](https://github.com/ml-explore/mlx) is a framework for running machine learning models on Apple Silicon.

    Convert your own models to MLX, or find community-converted ones at various quantizations [here](https://huggingface.co/mlx-community).

    ### Things you can do to improve this example:
    - [`prompt caching`](https://github.com/ml-explore/mlx-examples/blob/main/llms/README.md#long-prompts-and-generations)
    - completions / notebook mode
    - assistant pre-fill
    """)
    return


@app.cell
def _(Path, snapshot_download):
    def get_model_path(path_or_hf_repo: str) -> Path:
        """
        Ensures the model is available locally. If the path does not exist locally,
        it is downloaded from the Hugging Face Hub.

        Args:
            path_or_hf_repo (str): The local path or Hugging Face repository ID of the model.

        Returns:
            Path: The path to the model.
        """
        model_path = Path(path_or_hf_repo)
        if model_path.exists():
            return model_path
        else:
            try:
                # If it doesn't exist locally, download it from Hugging Face
                return Path(
                    snapshot_download(
                        repo_id=path_or_hf_repo,
                        allow_patterns=[
                            "*.json",
                            "*.safetensors",
                            "*.py",
                            "tokenizer.model",
                            "*.tiktoken",
                            "*.txt",
                        ],
                    )
                )
            except Exception as e:
                raise ValueError(
                    f"Error downloading model from Hugging Face: {str(e)}"
                )

    return (get_model_path,)


@app.cell
def _(mo):
    MODEL_ID = mo.ui.text(
        label="Hugging Face Model Repo or Local Path",
        value="mlx-community/Llama-3.2-3B-Instruct-bf16",
        placeholder="Enter huggingfacerepo_id/model_id or local path",
        full_width=True,
    )

    load_model_button = mo.ui.run_button(label="Load Model")

    mo.hstack([MODEL_ID, load_model_button])
    return MODEL_ID, load_model_button


@app.cell
def _(MODEL_ID, get_model_path, load, load_model_button, mo):
    mo.stop(not load_model_button.value, "Click 'Load Model' to proceed")

    try:
        mo.output.append(
            "⏳ Fetching model... This may take a while if downloading from Hugging Face."
        )
        model_path = get_model_path(MODEL_ID.value)
        mo.output.append(f"📁 Model path: {model_path}")
        mo.output.append("🔄 Loading model into memory...")
        model, tokenizer = load(model_path)
        mo.output.append(f"✅ Model loaded successfully!")
    except Exception as e:
        mo.output.append(f"❌ Error loading model: {str(e)}")
        raise
    return model, tokenizer


@app.cell(hide_code=True)
def _(mo):
    # Create a text area for the system message
    system_message = mo.ui.text_area(
        value="You are a helpful AI assistant.",
        label="System Message",
        full_width=True,
        rows=3,
    )

    system_message  # display the system message
    return (system_message,)


@app.cell(hide_code=True)
def _(mo):
    temp_slider = mo.ui.slider(
        start=0.0, stop=2.0, step=0.1, value=0.7, label="Temperature Slider"
    )
    max_tokens = mo.ui.number(value=512, label="Max Tokens Per Turn")

    temp_slider, max_tokens  # display the inputs
    return max_tokens, temp_slider


@app.cell
def _(generate, max_tokens, mo, model, system_message, temp_slider, tokenizer):
    def mlx_chat_model(messages, config):
        # Include the system message as the first message
        chat_messages = [{"role": "system", "content": system_message.value}]

        # Add the rest of the messages
        chat_messages.extend(
            [{"role": msg.role, "content": msg.content} for msg in messages]
        )

        # Use the tokenizer's chat template if available
        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            prompt = tokenizer.apply_chat_template(
                chat_messages, tokenize=False, add_generation_prompt=True
            )
        else:
            # Fallback to simple concatenation if no chat template
            prompt = "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in chat_messages
            )
            prompt += "\nassistant:"

        # Generate the response
        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=int(max_tokens.value),  # Use the max_tokens input
            temp=float(temp_slider.value),  # Use the temperature slider
        )

        return response.strip()


    # Create the chat interface
    chatbot = mo.ui.chat(
        mlx_chat_model,
        prompts=[
            "Hello",
            "How are you?",
            "I'm doing great, how about you?",
        ],
    )

    # Display the chatbot
    chatbot
    return (chatbot,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Access the chatbot's historical messages with `chatbot.value`.
    """)
    return


@app.cell
def _(chatbot):
    # Display the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()

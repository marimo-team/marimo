# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "huggingface-hub==0.26.2",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    from huggingface_hub import InferenceClient

    return InferenceClient, mo, os


@app.cell
def _():
    MODEL_NAME = "HuggingFaceH4/zephyr-7b-beta"
    return (MODEL_NAME,)


@app.cell(hide_code=True)
def _(MODEL_NAME, mo):
    mo.md(f"""
    # Chat with **{MODEL_NAME}**
    """)
    return


@app.cell
def _(max_tokens, mo, system_message, temperature, top_p):
    mo.hstack(
        [
            system_message,
            mo.vstack([temperature, top_p, max_tokens], align="end"),
        ],
    )
    return


@app.cell
def _(mo, respond):
    chat = mo.ui.chat(
        model=respond,
        prompts=["Tell me a joke.", "What is the square root of {{number}}?"],
    )
    chat
    return


@app.cell
def _(InferenceClient, MODEL_NAME, os):
    """
    For more information on `huggingface_hub` Inference API support, please check the docs: https://huggingface.co/docs/huggingface_hub/v0.26.2/en/guides/inference
    """

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("HF_TOKEN not set, may have limited access.")

    client = InferenceClient(
        MODEL_NAME,
        token=hf_token,
    )
    return (client,)


@app.cell
def _(client, mo):
    # Create UI controls
    system_message = mo.ui.text_area(
        value="You are a friendly Chatbot.",
        label="System message",
    )
    max_tokens = mo.ui.slider(
        start=1,
        stop=2048,
        value=512,
        step=1,
        label="Max new tokens",
        show_value=True,
    )
    temperature = mo.ui.slider(
        start=0.1,
        stop=4.0,
        value=0.7,
        step=0.1,
        label="Temperature",
        show_value=True,
    )
    top_p = mo.ui.slider(
        start=0.1,
        stop=1.0,
        value=0.95,
        step=0.05,
        label="Top-p (nucleus sampling)",
        show_value=True,
    )

    # Add more configuration options if needed.


    # Create chat callback
    def respond(messages: list[mo.ai.ChatMessage], config):
        chat_messages = [{"role": "system", "content": system_message.value}]

        for message in messages:
            parts = []
            # Add text
            parts.append({"type": "text", "text": message.content})

            # Add attachments
            if message.attachments:
                for attachment in message.attachments:
                    content_type = attachment.content_type or ""
                    # This example only supports image attachments
                    if content_type.startswith("image"):
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": attachment.url},
                            }
                        )
                    else:
                        raise ValueError(
                            f"Unsupported content type {content_type}"
                        )

            chat_messages.append({"role": message.role, "content": parts})

        response = client.chat_completion(
            chat_messages,
            max_completion_tokens=max_tokens.value,
            temperature=temperature.value,
            top_p=top_p.value,
            stream=False,
        )

        # You can return strings, markdown, charts, tables, dataframes, and more.
        return response.choices[0].message.content

    return max_tokens, respond, system_message, temperature, top_p


if __name__ == "__main__":
    app.run()

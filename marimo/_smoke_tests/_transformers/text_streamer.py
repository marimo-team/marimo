# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "accelerate==1.5.2",
#     "marimo",
#     "python-lsp-ruff==2.2.2",
#     "python-lsp-server==1.12.2",
#     "torch==2.6.0",
#     "transformers==4.50.3",
#     "websockets==15.0.1",
# ]
# ///

import marimo

__generated_with = "0.12.0"
app = marimo.App(width="medium")


@app.cell
def _():
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        pipeline,
        TextIteratorStreamer,
    )

    _model_small = AutoModelForCausalLM.from_pretrained(
        "sshleifer/tiny-gpt2", device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained("sshleifer/tiny-gpt2")
    pipeline = pipeline("text-generation", model="sshleifer/tiny-gpt2")
    streamer = TextIteratorStreamer(tokenizer)
    return (
        AutoModelForCausalLM,
        AutoTokenizer,
        TextIteratorStreamer,
        pipeline,
        streamer,
        tokenizer,
    )


@app.cell
def _(pipeline, streamer):
    pipeline("Say something: ", streamer=streamer)

    streamer
    return


if __name__ == "__main__":
    app.run()

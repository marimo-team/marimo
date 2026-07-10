# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "openai==1.53.0",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    chat = mo.ui.chat(
        mo.ai.llm.openai(
            "gpt-4o",
            system_message="""You are a helpful assistant that can
            parse my recipe and summarize them for me.
            Give me a title in the first line.""",
        ),
        allow_attachments=["image/png", "image/jpeg"],
        prompts=["What is the recipe?"],
    )
    chat
    return chat, mo


@app.cell
def _(chat, mo):
    mo.stop(not chat.value)

    last_message: str = chat.value[-1].content
    title = last_message.split("\n")[0]
    summary = "\n".join(last_message.split("\n")[1:])
    with open(f"{title}.md", "w") as f:
        f.write(summary)
        mo.status.toast("Receipt summary saved!", description=title)
    return


if __name__ == "__main__":
    app.run()

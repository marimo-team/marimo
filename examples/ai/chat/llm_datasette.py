# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "llm==0.16",
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.9.3"
app = marimo.App()


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""## Using <https://llm.datasette.io> with `mo.ui.chat()`""")
    return


@app.cell(hide_code=True)
def __(mo):
    mo.md("""To set a key, run: `llm keys set openai` in your terminal""")
    return


@app.cell
def __():
    import marimo as mo
    import llm
    return llm, mo


@app.cell
def __(llm, mo):
    model = llm.get_model("gpt-4o-mini")
    conversation = model.conversation()

    chat = mo.ui.chat(lambda messages: conversation.prompt(messages[-1].content))
    chat
    return chat, conversation, model


@app.cell
def __(chat):
    chat.value
    return


if __name__ == "__main__":
    app.run()

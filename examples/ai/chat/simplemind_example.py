# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "simplemind==0.1.3",
# ]
# ///

import marimo

__generated_with = "0.9.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def __(mo):
    mo.md(r"""## Using [simplemind](https://github.com/kennethreitz/simplemind) with `mo.ui.chat()`""")
    return


@app.cell(hide_code=True)
def __():
    import marimo as mo
    import os
    import simplemind as sm
    return mo, os, sm


@app.cell(hide_code=True)
def __(__file__, mo, os):
    has_set_env = os.environ.get("OPENAI_API_KEY") is not None
    mo.md(f"""
    Missing OpenAI API key. Re-run this notebook with the following command:

    ```bash
    export OPENAI_API_KEY='sk-'
    marimo edit {__file__}
    ```
    """).callout("warn") if not has_set_env else ""
    return (has_set_env,)


@app.cell
def __(mo):
    get_logs, set_logs = mo.state([], allow_self_loops=True)
    return get_logs, set_logs


@app.cell
def __(set_logs, sm):
    def add_log(value):
        return set_logs(lambda logs: logs + [value])


    class LoggingPlugin(sm.BasePlugin):
        def pre_send_hook(self, conversation):
            add_log(
                f"Sending conversation with {len(conversation.messages)} messages"
            )

        def add_message_hook(self, conversation, message):
            add_log(f"Adding message to conversation: {message.text}")

        def cleanup_hook(self, conversation):
            add_log(
                f"Cleaning up conversation with {len(conversation.messages)} messages"
            )

        def initialize_hook(self, conversation):
            add_log("Initializing conversation")

        def post_send_hook(self, conversation, response):
            add_log(f"Received response: {response.text}")
    return LoggingPlugin, add_log


@app.cell
def __(LoggingPlugin, mo, sm):
    conversation = sm.create_conversation(
        llm_model="gpt-4o", llm_provider="openai"
    )
    conversation.add_plugin(LoggingPlugin())


    def on_message(messages):
        conversation.add_message("user", messages[-1].content)
        return conversation.send().text


    chat = mo.ui.chat(on_message)
    return chat, conversation, on_message


@app.cell
def __(chat, get_logs, mo):
    logs = list(reversed(get_logs()))

    mo.hstack(
        [chat, mo.ui.table(logs, selection=None)],
        widths="equal",
    )
    return (logs,)


@app.cell
def __(chat):
    chat.value
    return


if __name__ == "__main__":
    app.run()

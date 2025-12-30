import marimo

__generated_with = "0.18.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import os
    return mo, os


@app.cell
def _(mo):
    mo.md(r"""
    # Pydantic-AI 🤖

    [Pydantic AI](https://ai.pydantic.dev/) is a modern framework to build applications that interact with LLMs. Key features include

    *   ✨ **Structured Outputs:** Force LLMs to return clean, structured data (like JSON) that conforms to your Pydantic models.
    *   ✅ **Validation & Type-Safety:** Use Pydantic's validation and Python's type hints to ensure data integrity and make your code robust.
    *   🧠 **Reasoning & Tool Use:** Define output models for complex reasoning tasks and reliable function calling (tool use).

    The following example uses [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to build a chatbot backed by Pydantic-AI & Google.
    """)
    return


@app.cell
def _(mo, os):
    os_key = os.environ.get("GOOGLE_AI_API_KEY")
    input_key = mo.ui.text(label="Google AI API key", kind="password")
    input_key if not os_key else None
    return


@app.cell
def _(os):
    from pydantic_ai import Agent
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider

    provider = GoogleProvider(api_key=os.getenv("GOOGLE_AI_API_KEY"))
    model = GoogleModel("gemini-2.5-flash", provider=provider)
    settings = GoogleModelSettings(
        google_thinking_config={"include_thoughts": True}
    )

    agent = Agent(
        model,
        instructions="You are a senior software engineer experienced in Python, React and Typescript.",
        model_settings=settings,
    )
    return (agent,)


@app.cell
def _(agent, mo):
    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(agent),
        prompts=[
            "Write the fibonacci function in Python",
            "Who is Ada Lovelace?",
            "What is marimo?",
        ],
        allow_attachments=True,
    )
    chatbot
    return (chatbot,)


@app.cell
def _(chatbot):
    chatbot.value
    return


if __name__ == "__main__":
    app.run()

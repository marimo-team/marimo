import marimo

__generated_with = "0.19.2"
app = marimo.App(width="medium")

with app.setup(hide_code=True):
    import marimo as mo
    import os
    import httpx

    from pydantic_ai import Agent, RunContext, BinaryImage
    from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
    from pydantic_ai.providers.google import GoogleProvider
    from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
    from pydantic_ai.providers.anthropic import AnthropicProvider
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.models.openai import (
        OpenAIResponsesModel,
        OpenAIResponsesModelSettings,
    )
    from pydantic import BaseModel
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Pydantic-AI 🤖

    [Pydantic AI](https://ai.pydantic.dev/) is a modern framework to build applications that interact with LLMs. Key features include

    *   ✨ **Structured Outputs:** Force LLMs to return clean, structured data (like JSON) that conforms to your Pydantic models.
    *   ✅ **Validation & Type-Safety:** Use Pydantic's validation and Python's type hints to ensure data integrity and make your code robust.
    *   🧠 **Reasoning & Tool Use:** Define output models for complex reasoning tasks and reliable function calling (tool use).

    The following example uses [`mo.ui.chat`](https://docs.marimo.io/api/inputs/chat.html#marimo.ui.chat) to build a chatbot backed by Pydantic-AI.
    """)
    return


@app.cell(hide_code=True)
def _():
    structured = mo.ui.checkbox(label="Structured outputs")
    thinking = mo.ui.checkbox(label="Reasoning")
    fetch_dog_tool = mo.ui.checkbox(label="Fetch dog pics tool")

    models = mo.ui.dropdown(
        options={
            "Gemini 2.5 Flash": "gemini-2.5-flash",
            "Claude Haiku 4.5": "claude-haiku-4-5",
            "GPT 5 Nano": "gpt-5-nano",
            "GPT 5 (multimodal)": "gpt-5",
        },
        value="Gemini 2.5 Flash",
        label="Choose a model",
    )

    mo.vstack([models, structured, thinking, fetch_dog_tool])
    return fetch_dog_tool, models, structured, thinking


@app.cell(hide_code=True)
def _(models):
    model_name = models.value
    if model_name.startswith("gemini"):
        env_key = "GOOGLE_AI_API_KEY"
    elif model_name.startswith("claude"):
        env_key = "ANTHROPIC_API_KEY"
    elif model_name.startswith("gpt"):
        env_key = "OPENAI_API_KEY"
    else:
        raise NotImplementedError

    os_key = os.environ.get(env_key)
    input_key = mo.ui.text(label="API key", kind="password")
    input_key if not os_key else None
    return input_key, model_name, os_key


@app.function
def get_model(
    model_name: str, thinking: bool, api_key: str
) -> tuple[Model, ModelSettings]:
    model_name = model_name.lower()

    if model_name.startswith("gemini"):
        provider = GoogleProvider(api_key=api_key)
        model = GoogleModel(model_name, provider=provider)
        settings = GoogleModelSettings(
            google_thinking_config={
                "include_thoughts": True if thinking else False
            }
        )
    elif model_name.startswith("claude"):
        model = AnthropicModel(
            model_name, provider=AnthropicProvider(api_key=api_key)
        )
        settings = AnthropicModelSettings(
            anthropic_thinking={"type": "enabled", "budget_tokens": 1024}
            if thinking
            else {"type": "disabled"},
        )
    elif model_name.startswith("gpt"):
        model = OpenAIResponsesModel(
            model_name, provider=OpenAIProvider(api_key=api_key)
        )
        settings = (
            OpenAIResponsesModelSettings(
                openai_reasoning_effort="low",
                openai_reasoning_summary="detailed",
            )
            if thinking
            else OpenAIResponsesModelSettings()
        )
    else:
        raise NotImplementedError

    return model, settings


@app.cell(hide_code=True)
def _(
    fetch_dog_tool,
    input_key,
    model_name,
    models,
    os_key,
    structured,
    thinking,
):
    class CodeOutput(BaseModel):
        code: str
        time_complexity: str
        memory_complexity: str
        algorithm_complexity: int


    api_key = input_key.value or os_key
    model, settings = get_model(models.value, thinking.value, api_key)

    output_type = str
    if "image" in model_name or model_name == "gpt-5":
        output_type = BinaryImage | str
    elif structured.value:
        output_type = [CodeOutput, str]

    agent = Agent(
        model,
        output_type=output_type,
        instructions="You are a senior software engineer experienced in Python, React and Typescript.",
        model_settings=settings,
    )

    if fetch_dog_tool.value:

        @agent.tool
        def fetch_dog_picture_url(ctx: RunContext[str]) -> str:
            """Returns URL of dog picture"""
            response_json = httpx.get(
                "https://dog.ceo/api/breeds/image/random"
            ).json()
            if "message" in response_json:
                return response_json["message"]
            else:
                return "Error fetching dog URL"
    return (agent,)


@app.cell
def _(agent):
    chatbot = mo.ui.chat(
        mo.ai.llm.pydantic_ai(agent),
        prompts=[
            "Write the fibonacci function in Python",
            "Who is Ada Lovelace?",
            "What is marimo?",
            "I need dogs (render as markdown)",
        ],
        allow_attachments=True,
        show_configuration_controls=True,
    )
    chatbot
    return (chatbot,)


@app.cell
def _(chatbot):
    chatbot.value
    return


@app.cell
def _():
    mo.md("""
    ## Custom Model Sample
    """)
    return


@app.cell
def _():
    import uuid
    import pydantic_ai.ui.vercel_ai.response_types as vercel


    async def custom_model(messages, config):
        # Generate unique IDs for message parts
        reasoning_id = f"reasoning_{uuid.uuid4().hex}"
        text_id = f"text_{uuid.uuid4().hex}"
        tool_id = f"tool_{uuid.uuid4().hex}"

        # --- Stream reasoning/thinking ---
        yield vercel.StartStepChunk()
        yield vercel.ReasoningStartChunk(id=reasoning_id)
        yield vercel.ReasoningDeltaChunk(
            id=reasoning_id,
            delta="The user is asking about Van Gogh. I should fetch information about his famous works.",
        )
        yield vercel.ReasoningEndChunk(id=reasoning_id)

        # --- Stream tool call to fetch artwork information ---
        yield vercel.ToolInputAvailableChunk(
            tool_call_id=tool_id,
            tool_name="search_artwork",
            input={"artist": "Vincent van Gogh", "limit": 1},
        )
        yield vercel.ToolInputStartChunk(
            tool_call_id=tool_id, tool_name="search_artwork"
        )
        yield vercel.ToolInputDeltaChunk(
            tool_call_id=tool_id,
            input_text_delta='{"artist": "Vincent van Gogh", "limit": 1}',
        )

        # --- Tool output (simulated artwork search result) ---
        yield vercel.ToolOutputAvailableChunk(
            tool_call_id=tool_id,
            output={
                "title": "The Starry Night",
                "year": 1889,
                "museum": "Museum of Modern Art",
            },
        )

        # --- Stream text response ---
        yield vercel.TextStartChunk(id=text_id)
        yield vercel.TextDeltaChunk(
            id=text_id,
            delta="One of Vincent van Gogh's most iconic works is 'The Starry Night', painted in 1889. Here's the painting:\n\n",
        )

        # --- Embed the artwork image ---
        yield vercel.FileChunk(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg",
            media_type="image/jpeg",
        )
        yield vercel.TextDeltaChunk(
            id=text_id,
            delta="\nThis masterpiece is now housed at the Museum of Modern Art in New York and remains one of the most recognizable paintings in the world.",
        )
        yield vercel.TextEndChunk(id=text_id)
        yield vercel.FinishStepChunk()
        yield vercel.FinishChunk()


    custom_chat = mo.ui.chat(custom_model)
    custom_chat
    return (custom_chat,)


@app.cell
def _(custom_chat):
    custom_chat.value
    return


if __name__ == "__main__":
    app.run()

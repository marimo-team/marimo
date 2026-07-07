# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx==0.28.1",
#     "marimo>=0.21.1",
#     "pydantic==2.12.5",
# ]
# ///

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="medium")

with app.setup(hide_code=True):
    import marimo as mo
    import os
    import httpx

    from pydantic_ai import (
        Agent,
        BinaryImage,
        DeferredToolRequests,
        RunContext,
    )
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
    delete_file_tool = mo.ui.checkbox(label="Delete file tool (requires approval)")

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

    mo.vstack([models, structured, thinking, fetch_dog_tool, delete_file_tool])
    return delete_file_tool, fetch_dog_tool, models, structured, thinking


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
    delete_file_tool,
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

    # Tools that pause for human approval require `DeferredToolRequests`
    # in the output type; pydantic-ai returns it whenever a tool flagged
    # `requires_approval=True` is called.
    if delete_file_tool.value:
        if isinstance(output_type, list):
            output_type = [*output_type, DeferredToolRequests]
        else:
            output_type = [output_type, DeferredToolRequests]

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


    if delete_file_tool.value:

        @agent.tool_plain(requires_approval=True)
        def delete_file(path: str) -> str:
            """Pretend to delete the file at `path`."""
            return f"File {path!r} deleted"
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
            "Delete the file at path 'secrets.env'",
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


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Custom model sample

    `mo.ui.chat` accepts any async generator that yields Vercel AI SDK chunks.
    The model below is a hand-rolled showcase of every part the SDK knows
    about — reasoning, streamed tool input, file/source/data attachments,
    a deliberately failed tool, and a final tool that pauses for human
    approval.
    """)
    return


@app.cell(hide_code=True)
def _():
    import asyncio
    import uuid

    import pydantic_ai.ui.vercel_ai.response_types as vercel


    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"


    def _pending_approval(messages) -> dict | None:
        """Find a tool part the user just approved or denied, if any.

        After Approve/Deny, the SDK transitions the tool part on the last
        assistant message to `approval-responded` and auto-resumes. We
        look for that state on the most recent assistant turn so we know
        whether to start a fresh showcase or finish the deletion.
        """
        for message in reversed(messages):
            if message.role != "assistant":
                continue
            for part in message.raw_or_dumped_parts():
                if not isinstance(part, dict):
                    continue
                if not str(part.get("type", "")).startswith("tool-"):
                    continue
                if part.get("state") == "approval-responded":
                    return part
            return None
        return None


    async def _showcase_turn():
        reasoning_id = _new_id("reasoning")
        search_id = _new_id("tc")
        translate_id = _new_id("tc")
        delete_id = _new_id("tc")
        approval_id = _new_id("ap")
        intro_id = _new_id("text")
        followup_id = _new_id("text")
        error_text_id = _new_id("text")
        ask_id = _new_id("text")
        data_id = _new_id("data")

        # Message-level metadata round-trips on `message.metadata` in the UI.
        yield vercel.MessageMetadataChunk(
            message_metadata={"demo": "vercel-ai-sdk-showcase", "turn": 1}
        )

        # ── Step 1: think + run a tool that succeeds ──────────────────
        yield vercel.StartStepChunk()

        yield vercel.ReasoningStartChunk(id=reasoning_id)
        for chunk in [
            "The user wants the full tour. ",
            "I'll search for a famous painting, ",
            "compose an answer with citations and an image, ",
            "demonstrate an erroring tool, ",
            "and finally offer to clean up a temp file ",
            "behind a human-approval gate.",
        ]:
            yield vercel.ReasoningDeltaChunk(id=reasoning_id, delta=chunk)
            await asyncio.sleep(0.04)
        yield vercel.ReasoningEndChunk(id=reasoning_id)

        yield vercel.ToolInputStartChunk(
            tool_call_id=search_id, tool_name="search_artwork"
        )
        for delta in ['{"artist":', ' "Vincent van Gogh",', ' "limit": 1}']:
            yield vercel.ToolInputDeltaChunk(
                tool_call_id=search_id, input_text_delta=delta
            )
            await asyncio.sleep(0.04)
        yield vercel.ToolInputAvailableChunk(
            tool_call_id=search_id,
            tool_name="search_artwork",
            input={"artist": "Vincent van Gogh", "limit": 1},
        )
        yield vercel.ToolOutputAvailableChunk(
            tool_call_id=search_id,
            output={
                "title": "The Starry Night",
                "year": 1889,
                "museum": "Museum of Modern Art",
            },
        )

        yield vercel.FinishStepChunk()

        # ── Step 2: compose the answer with rich media ────────────────
        yield vercel.StartStepChunk()

        yield vercel.TextStartChunk(id=intro_id)
        for delta in [
            "One of Vincent van Gogh's most iconic works is ",
            "**The Starry Night**, painted in 1889. ",
            "Here is the painting:",
        ]:
            yield vercel.TextDeltaChunk(id=intro_id, delta=delta)
            await asyncio.sleep(0.04)
        yield vercel.TextEndChunk(id=intro_id)

        yield vercel.FileChunk(
            url=(
                "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/"
                "Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/"
                "1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg"
            ),
            media_type="image/jpeg",
        )

        yield vercel.SourceUrlChunk(
            source_id=_new_id("src"),
            url="https://www.moma.org/collection/works/79802",
            title="The Starry Night | MoMA",
        )
        yield vercel.SourceDocumentChunk(
            source_id=_new_id("src"),
            media_type="application/pdf",
            title="Faille catalogue raisonné, vol. III",
            filename="van-gogh-catalogue.pdf",
        )

        # Custom data-* parts let backends ship arbitrary structured
        # payloads to bespoke UI widgets without bending the text channel.
        yield vercel.DataChunk(
            id=data_id,
            type="data-artwork-card",
            data={
                "title": "The Starry Night",
                "year": 1889,
                "movement": "Post-Impressionism",
            },
        )

        yield vercel.TextStartChunk(id=followup_id)
        yield vercel.TextDeltaChunk(
            id=followup_id,
            delta=(
                "\n\nNext I'll try a translation tool that's expected to"
                " fail — handy for seeing how errors render."
            ),
        )
        yield vercel.TextEndChunk(id=followup_id)

        yield vercel.FinishStepChunk()

        # ── Step 3: a tool whose execution fails ──────────────────────
        yield vercel.StartStepChunk()

        yield vercel.ToolInputStartChunk(
            tool_call_id=translate_id, tool_name="translate"
        )
        yield vercel.ToolInputAvailableChunk(
            tool_call_id=translate_id,
            tool_name="translate",
            input={"text": "Sterrennacht", "from": "nl", "to": "klingon"},
        )
        yield vercel.ToolOutputErrorChunk(
            tool_call_id=translate_id,
            error_text="UnsupportedLanguage: 'klingon' is not a supported target.",
        )

        yield vercel.TextStartChunk(id=error_text_id)
        yield vercel.TextDeltaChunk(
            id=error_text_id,
            delta="That call failed, as expected — moving on.",
        )
        yield vercel.TextEndChunk(id=error_text_id)

        yield vercel.FinishStepChunk()

        # ── Step 4: ask for approval, then stop ───────────────────────
        yield vercel.StartStepChunk()

        yield vercel.TextStartChunk(id=ask_id)
        yield vercel.TextDeltaChunk(
            id=ask_id,
            delta=(
                "I'd like to delete the search cache file. "
                "Approve below to proceed, or deny to keep it."
            ),
        )
        yield vercel.TextEndChunk(id=ask_id)

        yield vercel.ToolInputStartChunk(
            tool_call_id=delete_id, tool_name="delete_file"
        )
        yield vercel.ToolInputAvailableChunk(
            tool_call_id=delete_id,
            tool_name="delete_file",
            input={"path": "/tmp/van-gogh-search.cache"},
        )
        yield vercel.ToolApprovalRequestChunk(
            approval_id=approval_id, tool_call_id=delete_id
        )

        yield vercel.FinishStepChunk()
        yield vercel.FinishChunk(finish_reason="tool-calls")


    async def _resume_after_approval(pending: dict):
        tool_call_id = pending["toolCallId"]
        approval = pending.get("approval") or {}
        approved = bool(approval.get("approved"))
        path = (pending.get("input") or {}).get("path", "<unknown>")

        text_id = _new_id("text")

        yield vercel.MessageMetadataChunk(
            message_metadata={
                "demo": "vercel-ai-sdk-showcase",
                "turn": 2,
                "approval": approval,
            }
        )
        yield vercel.StartStepChunk()

        if approved:
            yield vercel.ToolOutputAvailableChunk(
                tool_call_id=tool_call_id,
                output={"deleted": True, "path": path},
            )
            yield vercel.TextStartChunk(id=text_id)
            yield vercel.TextDeltaChunk(
                id=text_id, delta=f"Done — `{path}` has been removed."
            )
            yield vercel.TextEndChunk(id=text_id)
        else:
            yield vercel.ToolOutputDeniedChunk(tool_call_id=tool_call_id)
            yield vercel.TextStartChunk(id=text_id)
            yield vercel.TextDeltaChunk(
                id=text_id,
                delta=(
                    f"No problem — I'll leave `{path}` alone. "
                    f"Reason: {approval.get('reason') or 'no reason given'}."
                ),
            )
            yield vercel.TextEndChunk(id=text_id)

        yield vercel.FinishStepChunk()
        yield vercel.FinishChunk(finish_reason="stop")


    async def custom_model(messages, config):
        del config

        pending = _pending_approval(messages)
        if pending is not None:
            async for chunk in _resume_after_approval(pending):
                yield chunk
            return

        async for chunk in _showcase_turn():
            yield chunk


    custom_chat = mo.ui.chat(
        custom_model,
        prompts=[
            "Run the full Vercel AI SDK part showcase",
            "Show me reasoning, citations, and an approval-gated tool",
        ],
    )
    custom_chat
    return (custom_chat,)


@app.cell
def _(custom_chat):
    custom_chat.value
    return


if __name__ == "__main__":
    app.run()

import marimo

__generated_with = "0.19.2"
app = marimo.App(width="medium", auto_download=["html"])


@app.cell
def _():
    import uuid
    import time
    import asyncio
    import pydantic_ai.ui.vercel_ai.response_types as vercel
    return asyncio, time, uuid, vercel


@app.cell
def _(
    async_no_streaming_text,
    async_streaming_chunks,
    async_streaming_text,
    mo,
    sync_no_streaming_object,
    sync_no_streaming_text,
    sync_streaming_text,
):
    model = mo.ui.dropdown(
        [
            async_streaming_chunks,
            async_streaming_text,
            async_no_streaming_text,
            sync_streaming_text,
            sync_no_streaming_text,
            sync_no_streaming_object,
        ],
        value=async_streaming_text,
        label="Select Model",
    )
    model
    return (model,)


@app.cell
def _(mo, model):
    chat = mo.ui.chat(model.value)
    chat
    return (chat,)


@app.cell
def _(chat):
    chat.value
    return


@app.cell
def _(uuid, vercel):
    async def async_streaming_chunks(messages, config):
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
    return (async_streaming_chunks,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(asyncio):
    async def async_streaming_text(messages, config):
        await asyncio.sleep(1)
        yield "This is a simple text-only response."
        await asyncio.sleep(1)
        yield " It does not include reasoning or tool calls."
        await asyncio.sleep(1)
        yield " Have a nice day!"
    return (async_streaming_text,)


@app.cell
def _(time):
    def sync_streaming_text(messages, config):
        time.sleep(1)
        yield "This"
        time.sleep(1)
        yield " is simple "
        time.sleep(1)
        yield " streaming."
    return (sync_streaming_text,)


@app.cell
def _(asyncio):
    async def async_no_streaming_text(messages, config):
        await asyncio.sleep(1)
        return f"**echo**: _{messages[-1].content}_"
    return (async_no_streaming_text,)


@app.cell
def _(time):
    def sync_no_streaming_text(messages, config):
        time.sleep(1)
        return f"**echo**: _{messages[-1].content}_"
    return (sync_no_streaming_text,)


@app.cell
def _(mo, time):
    def sync_no_streaming_object(messages, config):
        time.sleep(1)
        return mo.ui.table([1, 2, 3, messages[-1].content])
    return (sync_no_streaming_object,)


if __name__ == "__main__":
    app.run()

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pandas==2.3.1",
# ]
# ///

import marimo

__generated_with = "0.14.17"
app = marimo.App(width="columns")


@app.cell(column=0)
def _():
    from marimo._server.ai.providers import AnyLLMProvider, AnyProviderConfig
    from marimo._server.ai.tools import Tool
    from marimo._ai._types import ChatMessage
    from marimo._config.manager import get_default_config_manager
    return (
        AnyLLMProvider,
        AnyProviderConfig,
        ChatMessage,
        Tool,
        get_default_config_manager,
    )


@app.cell
def _(AnyProviderConfig, config, messages, tools):
    from any_llm import prepare_tools


    def print_stream(stream):
        for i in stream:
            print(i)


    def basic_query(provider, raw=False):
        system = "Answer the user. Narate why you are choosing a tool"
        res = provider.stream_completion(
            messages=[messages],
            system_prompt=system,
            max_tokens=8192,
        )
        if raw:
            return res
        return provider.as_stream_response(res)


    def get_config(key: str):
        return AnyProviderConfig(
            base_url=None, api_key=config[key]["api_key"], tools=tools
        )
    return basic_query, get_config, print_stream


@app.cell
def _(get_default_config_manager):
    config = get_default_config_manager(current_path=None).get_config(
        hide_secrets=False
    )["ai"]
    return (config,)


@app.cell(hide_code=True)
def _(Tool):
    tools = [
        Tool(
            source="local",
            mode="act",
            name="get_weather",
            description="get the weather",
            parameters={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Parameter location of type str",
                    },
                    "unit": {
                        "type": "string",
                        "description": "Parameter unit of type str",
                    },
                },
                "required": ["location"],
            },
        )
    ]
    return (tools,)


@app.cell
def _(ChatMessage):
    # messages = ChatMessage(role="user", content="Hi, im a human.")
    messages = ChatMessage(role="user", content="What is the weather in Denver.")
    return (messages,)


@app.cell(column=1)
def _(AnyLLMProvider, basic_query, get_config, print_stream):
    openai = AnyLLMProvider(
        "openai/gpt-4o",
        get_config("open_ai"),
    )
    print_stream(basic_query(openai))
    print_stream(basic_query(openai, raw=True))
    return


@app.cell
def _(AnyLLMProvider, basic_query, get_config, print_stream):
    openai_thinking = AnyLLMProvider(
        "openai/o4-mini",
        get_config("open_ai"),
    )
    print_stream(basic_query(openai_thinking))
    print_stream(basic_query(openai_thinking, raw=True))
    return


@app.cell(column=2)
def _(AnyLLMProvider, basic_query, get_config, print_stream):
    gemini = AnyLLMProvider(
        "google/gemini-2.0-flash",
        get_config("google"),
    )
    print_stream(basic_query(gemini))
    print_stream(basic_query(gemini, raw=True))
    return


@app.cell
def _(AnyLLMProvider, basic_query, get_config, print_stream):
    anthropic = AnyLLMProvider(
        "anthropic/claude-3-5-sonnet-latest",
        get_config("anthropic"),
    )
    print_stream(basic_query(anthropic))
    return


@app.cell(column=3)
def _(AnyLLMProvider, basic_query, get_config, mo):
    MODELS = [
        # Anthropic
        "anthropic/claude-opus-4-1-20250805",
        "anthropic/claude-opus-4-20250514",
        "anthropic/claude-sonnet-4-20250514",
        "anthropic/claude-3-7-sonnet-latest",
        "anthropic/claude-3-5-sonnet-latest",
        "anthropic/claude-3-5-haiku-latest",
        # DeepSeek
        # "deepseek/deepseek-v3",
        # "deepseek/deepseek-r1",
        # Google
        "google/gemini-2.5-flash",
        # "google/gemini-2.5-pro", # broken response
        "google/gemini-2.0-flash",
        "google/gemini-2.0-flash-lite",
        # OpenAI
        # "openai/o3",
        "openai/o4-mini",
        # "openai/gpt-4.5", # not working
        "openai/gpt-4.1",
        "openai/gpt-4o",
        # "openai/gpt-3.5-turbo", # not working
        # AWS Bedrock Models
        # "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        # "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        # "bedrock/anthropic.claude-3-7-sonnet-20250219-v1:0",
        # "bedrock/meta.llama3-3-70b-instruct-v1:0",
        # "bedrock/cohere.command-r-plus-v1",
    ]

    results = {}


    @mo.cache()
    def query(model):
        provider = model.split("/")[0].replace("openai", "open_ai")

        provider = AnyLLMProvider(
            model,
            get_config(provider),
        )
        return list(basic_query(provider))


    for model in MODELS:
        print("querying model", model)
        results[model] = query(model)
    return (results,)


@app.cell
def _(results):
    results
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()

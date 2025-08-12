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


if __name__ == "__main__":
    app.run()

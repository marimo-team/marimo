# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anthropic==0.64.0",
#     "any-llm-sdk[anthropic]==0.12.1",
#     "google-genai==1.30.0",
#     "marimo",
#     "polars==1.32.3",
#     "protobuf==5.29.5",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    models_csv = """
    name,model,description,provider,roles,thinking
    Claude 3 Haiku,claude-3-haiku-20240307,Fastest model optimized for speed and efficiency,anthropic,"chat, edit",False
    Claude 3.5 Haiku,claude-3-5-haiku-20241022,Fast and efficient model with excellent performance for everyday tasks,anthropic,"chat, edit",False
    Claude 3.5 Sonnet v2,claude-3-5-sonnet-20241022,High-performance model with advanced coding and reasoning capabilities,anthropic,"chat, edit, code, vision",False
    Claude Opus 4,claude-opus-4-20250514,World's best coding model with sustained performance on complex tasks,anthropic,"chat, edit, code, reasoning, vision",True
    Claude Opus 4.1,claude-opus-4-1-20250805,Latest flagship model with hybrid reasoning capabilities,anthropic,"chat, edit, reasoning, vision",True
    Claude Sonnet 3.7,claude-3-7-sonnet-20250219,Hybrid AI reasoning model with rapid or thoughtful responses,anthropic,"chat, edit, reasoning, vision",True
    Claude Sonnet 4,claude-sonnet-4-20250514,Superior coding and reasoning while responding precisely to instructions,anthropic,"chat, edit, code, reasoning, vision",True
    GPT-4.1,gpt-4.1,"Fast, highly intelligent model with largest context window",azure,"chat, edit, code",False
    GPT-4o,gpt-4o,"Fast, intelligent, flexible GPT model with multimodal capabilities",azure,"chat, edit, vision",False
    GPT-5,gpt-5,The best model for coding and agentic tasks across domains,azure,"chat, edit, code, agent",False
    GPT-5 Mini,gpt-5-mini,"A faster, cost-efficient version of GPT-5 for well-defined tasks",azure,"chat, edit",False
    o1-mini,o1-mini,Faster and cheaper reasoning model,azure,"reasoning, math",True
    o1-preview,o1-preview,Reasoning model with advanced problem solving capabilities,azure,"reasoning, math, code",True
    Amazon Nova Lite,amazon.nova-lite-v1:0,Fast and cost-effective multimodal model,bedrock,"chat, edit, vision",False
    Amazon Nova Micro,amazon.nova-micro-v1:0,Ultra-fast text-only model for simple tasks,bedrock,"chat, edit",False
    Amazon Nova Premier,amazon.nova-premier-v1:0,High-performance multimodal model for complex reasoning tasks,bedrock,"chat, edit, vision, reasoning",False
    Amazon Nova Pro,amazon.nova-pro-v1:0,Balanced multimodal model for general-purpose applications,bedrock,"chat, edit, vision",False
    Claude 3.5 Haiku,anthropic.claude-3-5-haiku-20241022-v1:0,Fast and efficient model for everyday tasks,bedrock,"chat, edit",False
    Claude 3.5 Sonnet v2,anthropic.claude-3-5-sonnet-20241022-v1:0,High-performance model with advanced coding capabilities,bedrock,"chat, edit, code, vision",False
    Claude Opus 4.1,anthropic.claude-opus-4-1-20250805-v1:0,Latest flagship model with hybrid reasoning capabilities,bedrock,"chat, edit, reasoning, vision",True
    Claude Sonnet 3.7,us.anthropic.claude-3-7-sonnet-20250219-v1:0,Hybrid reasoning model with rapid or thoughtful responses (uses inference profile),bedrock,"chat, edit, reasoning, vision",True
    Claude Sonnet 4,anthropic.claude-sonnet-4-20250514-v1:0,Superior coding and reasoning model,bedrock,"chat, edit, code, reasoning, vision",True
    DeepSeek R1,deepseek.deepseek-r1-671b-instruct-v1:0,Advanced reasoning model with step-by-step thinking,bedrock,"reasoning, math, code",True
    Meta Llama 3.2 90B Vision,meta.llama3-2-90b-instruct-v1:0,Large multimodal model with vision capabilities,bedrock,"chat, edit, vision",False
    Meta Llama 3.3 70B,meta.llama3-3-70b-instruct-v1:0,Latest Meta model with improved capabilities,bedrock,"chat, edit, code",False
    Gemini 1.5 Flash,gemini-1.5-flash,Fast and cost-effective model for high-volume applications,google,"chat, edit",False
    Gemini 1.5 Pro,gemini-1.5-pro,Advanced multimodal model with extensive context understanding,google,"chat, edit, vision, code",False
    Gemini 2.0 Flash,gemini-2.0-flash,"Next generation features, speed, and realtime streaming",google,"chat, edit, vision, code",False
    Gemini 2.5 Flash,gemini-2.5-flash,Efficient workhorse model with controllable thinking budget,google,"chat, edit, reasoning",True
    Gemini 2.5 Flash-Lite,gemini-2.5-flash-lite,Most cost-efficient model supporting high throughput,google,"chat, edit",False
    Gemini 2.5 Pro,gemini-2.5-pro,Most intelligent and capable AI model with 1M token context window,google,"chat, edit, reasoning, vision, code",True
    Codellama 34B,codellama:34b,Specialized model optimized for code generation and programming,ollama,"code, edit",False
    DeepSeek R1 70B,deepseek-r1:70b,Open reasoning model with performance approaching leading models,ollama,"reasoning, math, code",True
    DeepSeek R1 7B,deepseek-r1:7b,Smaller reasoning model with step-by-step thinking,ollama,"reasoning, math",True
    Gemma 3 27B,gemma3:27b,"Current, most capable Google model that runs on a single GPU",ollama,"chat, edit, code, vision",False
    Llama 3.1 70B,llama3.1:70b,State-of-the-art model from Meta with 70B parameters,ollama,"chat, edit, code",False
    Llama 3.2 Vision 11B,llama3.2-vision:11b,Multimodal model with vision capabilities,ollama,"chat, edit, vision",False
    Llama 3.2 Vision 90B,llama3.2-vision:90b,Large multimodal model with advanced vision understanding,ollama,"chat, edit, vision",False
    Llava 34B,llava:34b,Advanced vision-language understanding model,ollama,"chat, vision",False
    Mistral 7B,mistral:7b,Efficient and powerful model for general-purpose tasks,ollama,"chat, edit",False
    Qwen 3 32B,qwen3:32b,Latest generation model with dense and MoE architectures,ollama,"chat, edit, code",True
    gpt-oss 120B,gpt-oss:120b,Most powerful open-weight model from OpenAI with agentic capabilities,ollama,"chat, reasoning, agent, code",True
    gpt-oss 20B,gpt-oss:20b,Medium-sized open-weight model for low latency tasks,ollama,"chat, agent",True
    GPT-4.1,gpt-4.1,"Fast, highly intelligent model with largest context window (1 million tokens)",openai,"chat, edit, code",False
    GPT-4.1 Mini,gpt-4.1-mini,"Balanced for intelligence, speed, and cost",openai,"chat, edit",False
    GPT-4o,gpt-4o,"Fast, intelligent, flexible GPT model with multimodal capabilities",openai,"chat, edit, vision",False
    GPT-4o Mini,gpt-4o-mini,"Fast, affordable small model for focused tasks",openai,"chat, edit",False
    GPT-5,gpt-5,The best model for coding and agentic tasks across domains,openai,"chat, edit, code, agent",False
    GPT-5 Mini,gpt-5-mini,"A faster, cost-efficient version of GPT-5 for well-defined tasks",openai,"chat, edit",False
    GPT-5 Nano,gpt-5-nano,"Fastest, most cost-efficient version of GPT-5",openai,"chat, edit",False
    o3,o3,Our most powerful reasoning model with chain-of-thought capabilities,openai,"reasoning, math, code",True
    o3-mini,o3-mini,A small model alternative to o3 for reasoning tasks,openai,"reasoning, math",True
    o3-pro,o3-pro,Version of o3 designed to think longer and provide most reliable responses,openai,"reasoning, math, code",True
    o4-mini,o4-mini,"Faster, more affordable reasoning model optimized for math, coding, and visual tasks",openai,"reasoning, code, vision",True
    """
    return (models_csv,)


@app.cell
def _(models_csv):
    import polars as pl
    import io

    df = pl.read_csv(io.BytesIO(models_csv.encode()))
    df
    return (df,)


@app.cell
def _():
    import any_llm
    import marimo as mo
    import anthropic
    return any_llm, mo


@app.function
def get_key(provider):
    from marimo._config.manager import get_default_config_manager

    config = get_default_config_manager(current_path=None).get_config(
        hide_secrets=False
    )["ai"]
    if provider == "openai":
        return config.get("open_ai", {}).get("api_key")
    return config.get(provider, {}).get("api_key")


@app.cell
def _(any_llm, mo):
    @mo.persistent_cache()
    def query(provider, model):
        key = get_key(provider)
        return any_llm.completion(
            model=f"{provider}/{model}",
            messages=[{"role": "user", "content": "hi"}],
            api_key=key,
        )
    return (query,)


@app.cell
def _(df, query):
    SKIP = {"azure", "bedrock", "ollama"}

    for record in df.to_dicts():
        provider = record["provider"]
        if provider in SKIP:
            continue
        model = record["model"]
        print(f"Testing {provider} / {model}")
        try:
            res = query(provider, model)
            print(f"✅ {provider} / {model}")
            print(res.choices[0].message.content)
        except Exception as e:
            print(f"❌ {e}")
    return


@app.cell
def _(query):
    others = [
        ["google", "codegemma"],
        ["google", "codegemma-2b"],
        ["google", "codegemma-7b"],
    ]

    for provider, model in others:
        print(f"Testing {provider} / {model}")
        try:
            res = query(provider, model)
            print(f"✅ {provider} / {model}")
            print(res.choices[0].message.content)
        except Exception as e:
            print(f"❌ {e}")
    return


@app.cell
def _():
    import google.genai as genai

    client = genai.Client(api_key=get_key("google"))

    for m in client.models.list():
        for action in m.supported_actions:
            if action == "generateContent":
                print(f"Model name: {m.name}")
                print(f"Display name: {m.display_name}")
                print(f"Description: {m.description}")
                print("-" * 80)
    return


if __name__ == "__main__":
    app.run()

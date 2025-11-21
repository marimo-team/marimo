# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "litellm>=1.70.0",
# ]
# ///

import marimo

__generated_with = "0.17.4"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Using mo.ai.llm.litellm - Access 100+ Providers
    
    The generic `mo.ai.llm.litellm` model gives you direct access to any provider 
    supported by litellm, including local models like Ollama, cloud providers like 
    Together AI, and aggregators like OpenRouter.
    
    Perfect for:
    - 🏠 Local models (Ollama, vLLM, etc.)
    - 🚀 New/experimental providers
    - 🌐 OpenRouter (100+ models, one API key)
    - 💰 Cost-effective alternatives
    """)
    return


@app.cell
def _(mo):
    # Select a provider/model
    provider_options = {
        "Ollama (Local)": "ollama/llama3",
        "Together AI": "together_ai/meta-llama/Llama-3-70b",
        "OpenRouter": "openrouter/anthropic/claude-3-opus",
        "Replicate": "replicate/meta/llama-2-70b-chat",
        "Hugging Face": "huggingface/meta-llama/Llama-2-7b-chat-hf",
    }
    
    provider_selector = mo.ui.dropdown(
        options=provider_options,
        value="ollama/llama3",
        label="Select Provider & Model"
    )
    
    api_key_input = mo.ui.text(
        label="API Key (leave empty for Ollama)",
        kind="password",
        placeholder="Optional - needed for cloud providers"
    )
    
    mo.vstack([
        provider_selector,
        api_key_input if provider_selector.value != "ollama/llama3" else None
    ])
    return api_key_input, provider_options, provider_selector


@app.cell
def _(api_key_input, mo, provider_selector):
    # Create chatbot with selected model
    model_id = provider_selector.value
    api_key = api_key_input.value if api_key_input.value else None
    
    # For cloud providers, stop if no API key
    needs_api_key = not model_id.startswith("ollama/")
    if needs_api_key and not api_key:
        mo.stop(
            True,
            mo.md(f"⚠️ **API key required** for {model_id.split('/')[0]}")
        )
    
    chatbot = mo.ui.chat(
        mo.ai.llm.litellm(
            model_id,
            system_message="You are a helpful AI assistant.",
            api_key=api_key,
        ),
        prompts=[
            "Hello! Tell me about yourself.",
            "What can you help me with?",
            "Explain quantum computing in simple terms.",
        ],
    )
    chatbot
    return api_key, chatbot, model_id, needs_api_key


@app.cell
def _(mo):
    mo.md("""
    ## How it works
    
    The `mo.ai.llm.litellm` model accepts any litellm-compatible model identifier:
    
    ```python
    # Local Ollama
    mo.ai.llm.litellm("ollama/llama3")
    
    # Together AI
    mo.ai.llm.litellm("together_ai/meta-llama/Llama-3-70b", api_key=key)
    
    # OpenRouter (100+ models with one API key)
    mo.ai.llm.litellm("openrouter/anthropic/claude-3-opus", api_key=key)
    ```
    
    ### Benefits
    
    ✅ **100+ providers** - Access any litellm-supported provider  
    ✅ **Local models** - Use Ollama, vLLM without API keys  
    ✅ **Cost-effective** - Try cheaper alternatives  
    ✅ **Future-proof** - New providers work immediately  
    
    ### Provider List
    
    See the complete list at: https://docs.litellm.ai/docs/providers
    """)
    return


@app.cell
def _(chatbot, mo):
    mo.md(f"""
    ## Chat History
    
    Total messages: {len(chatbot.value)}
    """)
    return


@app.cell
def _(chatbot):
    # Show the chat history
    chatbot.value
    return


if __name__ == "__main__":
    app.run()


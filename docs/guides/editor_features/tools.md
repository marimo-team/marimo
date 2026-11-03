## Available tools


## Web search and fetch

In any chat panel mode (**Manual**, **Ask**, **Agent**, or **Code mode**), marimo can give the assistant access to web search and URL fetching. These are [provider-adaptive capabilities](https://pydantic.dev/docs/ai/core-concepts/capabilities/#provider-adaptive-tools) from [Pydantic AI](https://ai.pydantic.dev): marimo enables them automatically based on your installed packages and the model you are using.

### How capabilities are enabled

marimo picks the best available option for each capability:

| Capability | Local fallback (installed in your environment) | Native (model provider supports it) |
|------------|-----------------------------------------------|-------------------------------------|
| **Web search** | DuckDuckGo search when `ddgs` is installed | Provider-native web search (e.g. Anthropic, OpenAI Responses) |
| **Web fetch** | URL fetching via `markdownify` when installed | Provider-native web fetch |
| **X search** | — | xAI models with native X search support |

Local fallbacks take priority when their packages are installed. Otherwise, marimo uses the provider's native tools when your configured model supports them.

### Install local web search and fetch

To enable web search and fetch on any model — including local models via Ollama — install the optional Pydantic AI extras:

```bash
pip install "pydantic-ai-slim[duckduckgo,web-fetch]"
```

### Use provider-native tools

When local packages are not installed, marimo enables native tools only if your model supports them. For example:

- **Anthropic** and **OpenAI Responses** models can use native web search and web fetch
- **xAI** models (e.g. `xai/grok-2-latest`) can use native web search and X search

Configure xAI in your `marimo.toml` or through the notebook settings — see the [xAI provider guide](../configuration/llm_providers.md#xai).


## Code mode

!!! warning "Experimental"
    Code mode gives the assistant direct access to your notebook's kernel so it can make destructive changes to your notebook.

Code mode is available from the chat panel mode selector. Instead of the inspection and editing tools above, the assistant uses a different toolset oriented around running Python in the live kernel:

| Tool / capability | Description |
|-------------------|-------------|
| **execute_code** | Run Python in the notebook kernel's scratchpad. The assistant uses this for all notebook mutations — adding cells, updating code, inspecting variables, and running logic. |
| **gotchas** | On-demand reference for name redefinition, cached module proxies, and other notebook traps. |
| **notebook-improvements** | On-demand reference for improving, optimizing, or cleaning up an existing notebook. |
| **rich-representations** | On-demand reference for custom widgets, visual encodings, and interactive output. |

Code mode loads the [marimo pair](../generate_with_ai/marimo_pair.md) skill as its system prompt, so the assistant follows the same conventions as external agent CLIs paired on your notebook.


## Related documentation

- [Model Context Protocol (MCP)](mcp.md) - Learn how to expose tools through the marimo MCP server
- [AI-assisted coding](ai_completion.md) - Learn about more AI coding features

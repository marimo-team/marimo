# In-editor AI assistance

> **Using coding agents? Try marimo pair instead.**
>
> To use coding agents such as Claude Code, Codex, or OpenCode, use [marimo
> pair](../generate_with_ai/marimo_pair.md) instead.

marimo's built-in AI features let you:

* edit notebook code, run cells, and more using a chat interface;
* refactor existing cells;
* supply variable values as context;
* complete code snippets with copilots.

## Connecting to a provider

Connect to an LLM provider through the notebook settings menu; both hosted and
local providers are available. See the [LLM providers
guide](../configuration/llm_providers.md) for detailed instructions.


<a id="chat-panel"></a>

## Chat sidebar panel

The chat panel in the sidebar lets you use AI to edit and generate
notebook code, run cells, and more. The **Notebook access** selector lets
you choose what the assistant can do:

- **Read only**: The assistant can read notebook code, outputs, and variable previews.
- **Suggest edits**: The assistant can read the notebook and propose cell changes for review.
- **Full access**: The assistant can read, edit, and run cells, with Python scratchpad access.

!!! warning "Full access can execute arbitrary Python code"
    Full access lets models execute arbitrary Python on your machine, and it can change
    notebook cells and runtime state without review. These changes can be destructive.

<video muted autoplay loop playsinline controls preload="metadata" width="100%"
  aria-label="Open Chat and start generating notebook cells">
  <source src="/_static/docs-chat-panel.mp4" type="video/mp4">
</video>

## Refactor existing cells

Make edits to an existing cell by inputting `Ctrl/Cmd-shift-e` while a cell is
focused. This opens a prompt box that has your cell's code as input.

<video muted autoplay loop playsinline controls preload="metadata" width="100%"
  aria-label="Refactor a cell with AI">
  <source src="/_static/docs-refactor-ai.mp4" type="video/mp4">
</video>

## Variable context

marimo provides models your notebook code as context. You can additionally
supply variables and their values by referencing them by name
with `@`. For example, to include the columns of a dataframe `df` in your
prompt, write `@df`.

<div align="center">
<figure>
<img src="/_static/docs-ai-variables.png" width="740px"/>
<figcaption>Pass variables to your prompt by tagging them with `@`.</figcaption>
</figure>
</div>


## Custom rules

You can customize how the AI assistant behaves by adding rules in the marimo
settings. These rules help ensure consistent code generation across all AI
providers.

<div align="center">
  <figure>
    <img src="/_static/docs-ai-completion-custom-assist-rules.png"/>
    <figcaption>Configure custom AI rules in settings</figcaption>
  </figure>
</div>

For example, you can add rules about:

* Preferred plotting libraries (matplotlib, plotly, altair)
* Data handling practices
* Code style conventions
* Error handling preferences

Example custom rules:

```
Use plotly for interactive visualizations and matplotlib for static plots
Prefer polars over pandas for data manipulation due to better performance
Include docstrings for all functions using NumPy style
Use Type hints for all function parameters and return values
Handle errors with try/except blocks and provide informative error messages
Follow PEP 8 style guidelines
When working with data:
- Use altair, plotly for declarative visualizations
- Prefer polars over pandas
- Ensure proper error handling for data operations
For plotting:
- Use px.scatter for scatter plots
- Use px.line for time series
- Include proper axis labels and titles
- Set appropriate color schemes
```

## Copilots

Copilots allow you to tab-complete code based on your notebook's context, similar to editors like Cursor.

<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-ai-completion-preview.mp4" type="video/mp4">
</video>

### GitHub Copilot

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

_GitHub Copilot is not yet available in our conda distribution; please install
marimo using `pip`/`uv` if you need Copilot._

#### Advanced configuration

You can customize GitHub Copilot's behavior by adding `copilot_settings` to your `marimo.toml` configuration file:

```toml title="marimo.toml"
[ai.github]
copilot_settings = { http = { proxy = "http://proxy.example.com:8888", proxyStrictSSL = true } }
```

Or in a more readable format:

```toml title="marimo.toml"
[ai.github.copilot_settings.http]
proxy = "http://proxy.example.com:8888"
proxyStrictSSL = true

[ai.github.copilot_settings.github-enterprise]
uri = "https://github.enterprise.com"  # For GitHub Enterprise users
```

Available configuration options (these are the same settings directory from the [npm package](https://github.com/orgs/github/packages/npm/package/copilot-language-server):

* **HTTP settings**: Configure proxy settings for network connections
    * `proxy`: HTTP proxy URL (e.g., `"http://proxy.example.com:8888"`)
    * `proxyStrictSSL`: Whether to verify SSL certificates for the proxy (default: `false`)
    * `proxyKerberosServicePrincipal`: Kerberos service principal for proxy authentication

* **Telemetry settings**: Control telemetry data collection
    * `telemetryLevel`: Level of telemetry to send - `"off"`, `"crash"`, `"error"`, or `"all"` (default: `"off"`)

* **GitHub Enterprise**: Configure GitHub Enterprise Server
    * `uri`: URL of your GitHub Enterprise Server instance

### Custom copilots

marimo also supports integrating with custom LLM providers for code completion suggestions. This allows you to use your own LLM service to provide in-line code suggestions based on internal providers or local models (e.g. Ollama). You may also use OpenAI, Anthropic, Google, or any other providers by providing your own API keys and configuration.

To configure a custom copilot:

1. Ensure you have an LLM provider that offers API access for code completion (either external or running locally)
2. Add the following configuration to your `marimo.toml` (or configure in the UI settings in the editor):

```toml title="marimo.toml"
[ai.models]
autocomplete_model = "provider/model-name"

[completion]
copilot = "custom"
```

The configuration options include:

* `autocomplete_model`: The specific model to use for inline autocompletion.
* `copilot`: The name of the copilot to use for code generation.

## Disable in-editor AI features

Disable in-editor AI features, and hide their associated user interfaces, with
the following configuration:

```toml title="marimo.toml"
[ai]
enabled = false

[completion]
copilot = false
```

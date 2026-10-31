# In-editor AI assistance

!!! tip "Using agents like Claude Code or OpenCode? Try marimo pair instead."

    This guide covers AI assistance built into the marimo editor.
    To work with coding agents such as Claude Code or OpenCode, use [marimo
    pair](../generate_with_ai/marimo_pair.md) instead.

marimo's editor lets you use AI to author and modify your notebook. Use AI to:

* generate new cells and refactor existing ones;
* complete code snippets with copilots.

Unlike traditional assistants that only have access to the text of your
program, marimo's assistant has access to the values of variables in memory,
letting it code against your dataframe and database schemas.

This guide provides an overview of these features and how to configure them.

<div align="center">
<video autoplay muted loop playsinline width="90%" height="90%" align="center">
  <source src="/_static/readme-generate-with-ai.mp4" type="video/mp4">
</video>
</div>

!!! tip "Locating your marimo.toml config file"

    Various instructions in this guide refer to the marimo.toml configuration
    file. Locate this file with `marimo config show | head`.

## Connecting to an LLM

Connect to an LLM through the notebook settings menu.

You can configure the following providers:

* OpenAI
* GitHub Copilot
* Anthropic
* AWS Bedrock
* Google AI
* Ollama
* and any OpenAI-compatible provider

See the [llm_providers](../configuration/llm_providers.md) guide for detailed
instructions on how to configure each provider.

## Generating cells with AI

marimo has built-in support for generating and refactoring code with LLMs.

**Enabling AI code generation.** To enable AI code generation, first install
required dependencies through the notebook settings.

<div align="center">
<figure>
<img src="/_static/docs-ai-install.png" width="740px"/>
<figcaption>Install required dependencies for AI generation through the notebook settings.</figcaption>
</figure>
</div>

Then configure your LLM provider through the AI tab in the settings menu; see
the section on [connecting your LLM](#connecting-to-an-llm) for detailed instructions.

### Variable context

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

### Generate new cells

#### Generate with AI button

At the bottom of every notebook is a button titled "Generate with AI". Click this
button to add entirely new cells to your notebook.

#### Chat panel

The chat panel on the left sidebar lets you chat with an LLM and ask questions
about your notebook. The LLM can also generate code cells that you can insert
into your notebook.

<iframe width="740" height="420" src="https://www.youtube.com/embed/4DC1E2UBwAM?si=zzrzl0VlvOU6JiZP" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" loading="lazy" allowfullscreen></iframe>

The chat panel currently supports the following modes:

- **Manual**: No tool access; the AI responds based only on the conversation and manually injected context
- **Ask**: Enables read-only [AI tools](tools.md) and [tools from added MCP Client servers](mcp.md#mcp-client) for context gathering, allowing the assistant to inspect your notebooks
- **Agent**: Enables all tools in **Ask Mode** plus additional tools to [edit notebook cells (add, remove, update) and run stale cells](tools.md#editing-agent-mode-only)
- **Code mode**: Gives the assistant access to the [notebook kernel](tools.md#code-mode) which allows the assistant to inspect the marimo runtime and manipulate the notebook in powerful ways.

### Refactor existing cells

Make edits to an existing cell by inputting `Ctrl/Cmd-shift-e` while a cell is
focused. This opens a prompt box that has your cell's code as input.

### Custom rules

You can customize how the AI assistant behaves by adding rules in the marimo settings. These rules help ensure consistent code generation across all AI providers. You can find more information about marimo's supported plotting libraries and data handling in the [plotting guide](../working_with_data/plotting.md#plotting) and [working with data guide](../working_with_data/index.md).

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

<div align="center">
<figure>
<img src="/_static/docs-ai-completion-gh.png" width="740px"/>
<figcaption>Follow these instructions.</figcaption>
</figure>
</div>

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
```

# AI completion

marimo comes with GitHub Copilot, a tool that helps you write code faster by
suggesting in-line code suggestions based on the context of your current code.

marimo also comes with the ability to use AI for refactoring a cell, finishing writing a cell, or writing a full cell from scratch.
This feature is currently experimental and is not enabled by default.

## GitHub Copilot

The marimo editor natively supports [GitHub Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code.

_Get started with Copilot_:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

!!! note "Installation Requirement"
    Copilot is not yet available in our conda distribution; please install
    marimo using ``pip`` if you need Copilot.

## Codeium Copilot

1. Go to the Codeium website and sign up for an account: <https://codeium.com/>
2. Install the browser extension: <https://codeium.com/chrome_tutorial>
3. Open the settings for the Chrome extension and click on "Get Token"
4. Right-click on the extension window and select "Inspect" to open the developer tools for the extension. Then click on "Network"
5. Copy the token and paste it into the input area, and then press "Enter Token"
6. This action will log a new API request in the **Network** tab. Click on "Preview" to get the API key.
7. Paste the API key in the marimo settings in the UI, or add it to your `marimo.toml` file as follows:

```toml title="marimo.toml"
[completion]
copilot = "codeium"
codeium_api_key = ""
```

### Alternative: Obtain Codeium API key using VS Code

1. Go to the Codeium website and sign up for an account: <https://codeium.com/>
2. Install the [Codeium Visual Studio Code extension](vscode:extension/codeium.codeium) (see [here](https://codeium.com/vscode_tutorial) for complete guide)
3. Sign in to your Codeium account in the VS Code extension
4. Select the Codeium icon on the Activity bar (left side), which opens the Codeium pane
5. Select the **Settings** button (gear icon) in the top-right corner of the Codeium pane

<div align="center">
  <figure>
    <img src="/_static/docs-ai-completion-codeium-vscode.png"/>
    <figcaption>Open Codeium settings</figcaption>
</figure>
</div>

6. Click the **Download** link under the **Extension Diagnostics** section
7. Open the diagnostic file and search for `apiKey`

<div align="center">
  <figure>
    <img src="/_static/docs-ai-completion-codeium-vscode-download-diagnostics.png"/>
    <figcaption>Download diagnostics file with API key</figcaption>
  </figure>
</div>

8. Copy the value of the `apiKey` to `.marimo.toml` in your home directory

```toml title="marimo.toml"
[completion]
codeium_api_key = "a1e8..."  # <-- paste your API key here
copilot = "codeium"
activate_on_typing = true
```

## Custom Copilot

marimo also supports integrating with custom LLM providers for code completion suggestions. This allows you to use your own LLM service to provide in-line code suggestions based on internal providers or local models (e.g. Ollama). You may also use OpenAI, Anthropic, or Google AI by providing your own API keys.

To configure a custom copilot:

1. Ensure you have an LLM provider that offers API access for code completion (either external or running locally)
2. Add the following configuration to your `marimo.toml` (or configure in the UI settings):

```toml title="marimo.toml"
[completion]
copilot = "custom"
api_key = "your-llm-api-key"
model = "your-llm-model-name"
base_url = "http://127.0.0.1:11434/v1" # or https://your-llm-api-endpoint.com
```

The configuration options include:

- `api_key`: Your LLM provider's API key. This may not be required for local models, so you can set it to any random string.
- `model`: The specific model to use for completion suggestions.
- `base_url`: The endpoint URL for your LLM provider's API

## Generate code with our AI assistant

marimo has built-in support for generating and refactoring code with AI, with a variety of providers. marimo works with hosted AI providers, such as OpenAI, Anthropic, and Google, as well as local models served via Ollama.

### Custom AI Rules

You can customize how the AI assistant behaves by adding rules in the marimo settings. These rules help ensure consistent code generation across all AI providers. You can find more information about marimo's supported plotting libraries and data handling in the [plotting guide](../working_with_data/plotting.md#plotting) and [working with data guide](../working_with_data/index.md).

<div align="center">
  <figure>
    <img src="/_static/docs-ai-completion-custom-assist-rules.png"/>
    <figcaption>Configure custom AI rules in settings</figcaption>
  </figure>
</div>

For example, you can add rules about:

- Preferred plotting libraries (matplotlib, plotly, altair)
- Data handling practices
- Code style conventions
- Error handling preferences

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

To locate your configuration file, run:

```bash
marimo config show
```

At the top, the path to your `marimo.toml` file will be shown. You can Ctrl/Cmd+click the path to open it in your editor. For more information about configuration, see the [Configuration Guide](../configuration/index.md).

Below we describe how to connect marimo to your AI provider. Once enabled, you can generate entirely new cells by clicking the "Generate with AI" button at the bottom of your notebook. You can also refactor existing cells by inputting `Ctrl/Cmd-Shift-e` in a cell, opening an input to modify the cell using AI.

<div align="center">
<figure>
<video src="/_static/ai-completion.mp4" controls="controls" width="100%" height="100%"></video>
<figcaption>Use AI to modify a cell by pressing `Ctrl/Cmd-Shift-e`.</figcaption>
</figure>
</div>

### Using OpenAI

1. Install openai: `pip install openai`

2. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.open_ai]
# Get your API key from https://platform.openai.com/account/api-keys
api_key = "sk-proj-..."
# Choose a model, we recommend "gpt-4-turbo"
model = "gpt-4-turbo"
# Available models: gpt-4-turbo-preview, gpt-4, gpt-3.5-turbo
# See https://platform.openai.com/docs/models for all available models

# Change the base_url if you are using a different OpenAI-compatible API
base_url = "https://api.openai.com/v1"
```

### Using Anthropic

To use Anthropic with marimo:

1. Sign up for an account at [Anthropic](https://console.anthropic.com/) and grab your [Anthropic Key](https://console.anthropic.com/settings/keys).
2. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.open_ai]
model = "claude-3-7-sonnet-20250219"
# or any model from https://docs.anthropic.com/en/docs/about-claude/models

[ai.anthropic]
api_key = "sk-ant-..."
```

### Using Google AI

To use Google AI with marimo:

1. Sign up for an account at [Google AI Studio](https://aistudio.google.com/app/apikey) and obtain your API key.
2. Install the Google AI Python client: `pip install google-generativeai`
3. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.open_ai]
model = "gemini-1.5-flash"
# or any model from https://ai.google.dev/gemini-api/docs/models/gemini

[ai.google]
api_key = "AI..."
```

### Using local models with Ollama { #using-ollama }

Ollama allows you to run open-source LLMs on your local machine. To integrate Ollama with marimo:

1. Download and install [Ollama](https://ollama.com/).
2. Download the model you want to use:

   ```bash
   # View available models at https://ollama.com/library
   ollama pull llama3.1
   ollama pull codellama  # recommended for code generation

   # View your installed models
   ollama ls
   ```

3. Start the Ollama server in a terminal:

   ```bash
   ollama serve
   # In a new terminal
   ollama run codellama  # or any model from ollama ls
   ```

4. Visit <http://127.0.0.1:11434> to confirm that the server is running.

!!! note "Port already in use"
    If you get a "port already in use" error, you may need to close an existing Ollama instance. On Windows, click the up arrow in the taskbar, find the Ollama icon, and select "Quit". This is a known issue (see [Ollama Issue #3575](https://github.com/ollama/ollama/issues/3575)). Once you've closed the existing Ollama instance, you should be able to run `ollama serve` successfully.

5. Open a new terminal and start marimo:

   ```bash
   marimo edit notebook.py
   ```

6. Add the following to your `marimo.toml`:

```toml title="marimo.toml"
[ai.open_ai]
api_key = "ollama" # This is not used, but required
model = "codellama" # or another model from `ollama ls`
base_url = "http://127.0.0.1:11434/v1"
```

### Using other AI providers

marimo supports OpenAI's API by default. Many providers offer OpenAI API-compatible endpoints, which can be used by simply changing the `base_url` in your configuration. For example, providers like [GROQ](https://console.groq.com/docs/openai) and [DeepSeek](https://platform.deepseek.com) follow this pattern.

??? tip "Using OpenAI-compatible providers (e.g., DeepSeek)"

    === "Via marimo.toml"

        Add the following configuration to your `marimo.toml` file:

        ```toml
        [ai.open_ai]
        api_key = "dsk-..." # Your provider's API key
        model = "deepseek-chat" # or "deepseek-reasoner"
        base_url = "https://api.deepseek.com/"
        ```

    === "Via UI Settings"

        1. Open marimo's Settings panel
        2. Navigate to the AI section
        3. Enter your provider's API key in the "OpenAI API Key" field
        4. Under AI Assist settings:
           - Set Base URL to your provider's endpoint (e.g., `https://api.deepseek.com`)
           - Set Model to your chosen model (e.g., `deepseek-chat` or `deepseek-reasoner`)

For a comprehensive list of compatible providers and their configurations, please refer to the [liteLLM Providers documentation](https://litellm.vercel.app/docs/providers).

For providers not compatible with OpenAI's API, please submit a [feature request](https://github.com/marimo-team/marimo/issues/new?template=feature_request.yaml) or "thumbs up" an existing one.

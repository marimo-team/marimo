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

_Note_: Copilot is not yet available in our conda distribution; please install
marimo using `pip` if you need Copilot.

## Codeium Copilot

1. Go to the Codeium website and sign up for an account: <https://codeium.com/>
2. Install the browser extension: <https://codeium.com/chrome_tutorial>
3. Open the settings for the Chrome extension and click on "Get Token"
4. Right-click on the extension window and select "Inspect" to open the developer tools for the extension. Then click on "Network"
5. Copy the token and paste it into the input area, and then press "Enter Token"
6. This action will log a new API request in the **Network** tab. Click on "Preview" to get the API key.
7. Paste the API key in the marimo settings in the UI, or add it to your `marimo.toml` file as follows:

```toml
[completion]
copilot = "codeium"
codeium_api_key = ""
```

## Generate code with our AI assistant

marimo has built-in support for generating and refactoring code with AI, with a
variety of providers. marimo works with both hosted AI providers, such as
OpenAI and Anthropic, as well as local models served via Ollama.

Below we describe how to connect marimo to your AI provider. Once enabled, you
can generate entirely new cells by clicking the "Generate with AI" button at
the bottom of your notebook. You can also refactor existing cells by inputting
`Ctrl/Cmd-Shift-e` in a cell, opening an input to modify the cell using AI.

<div align="center">
<figure>
<video src="/_static/ai-completion.mp4" controls="controls" width="100%" height="100%"></video>
<figcaption>Use AI to modify a cell by pressing `Ctrl/Cmd-Shift-e`.</figcaption>
</figure>
</div>

### Using OpenAI

1. Install openai: `pip install openai`

2. Add the following to your `marimo.toml`:

```toml
[ai.open_ai]
# Get your API key from https://platform.openai.com/account/api-keys
api_key = "sk-..."
# Choose a model, we recommend "gpt-4-turbo"
model = "gpt-4-turbo"
# Change the base_url if you are using a different OpenAI-compatible API
base_url = "https://api.openai.com/v1"
```

### Using Anthropic

To use Anthropic with marimo:

1. Sign up for an account at [Anthropic](https://console.anthropic.com/) and grab your [Anthropic Key](https://console.anthropic.com/settings/keys).
2. Add the following to your `marimo.toml`:

```toml
[ai.open_ai]
model = "claude-3-5-sonnet-20240620"
# or any model from https://docs.anthropic.com/en/docs/about-claude/models

[ai.anthropic]
api_key = "sk-..."
```

### Using other AI providers

marimo supports OpenAI's GPT-3.5 API by default. If your provider is compatible with OpenAI's API, you can use it by changing the `base_url` in the configuration.

For other providers not compatible with OpenAI's API, please submit a [feature request](https://github.com/marimo-team/marimo/issues) or "thumbs up" an existing one.

### Using local models with Ollama

Ollama allows you to run open-source LLMs (e.g. Llama 3.1, Phi 3, Mistral,
Gemma 2) on your local machine. To integrate Ollama with marimo:

1. Download and install [Ollama](https://ollama.com/).
2. Download the model you want to use:
   1. `ollama pull llama2`
   2. We also recommend `codellama` (code specific) or `llama3.1` (more advanced, but larger).
3. Start the Ollama server: `ollama run llama2`
4. Visit <http://localhost:11434> to confirm that the server is running.
5. Add the following to your `marimo.toml`:

```toml
[ai.open_ai]
api_key = "ollama" # This is not used, but required
model = "llama2" # or the model you downloaded from above
base_url = "http://localhost:11434/v1"
```

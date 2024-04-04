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

## Using AI to modify cells

This feature is currently experimental and is not enabled by default. To enable it:

1. Install openai: `pip install openai`

2. Add the following to your `~/.marimo.toml`:

```toml
[ai.open_ai]
# Get your API key from https://platform.openai.com/account/api-keys
api_key = "sk-..."
# Choose a model, we recommend "gpt-3.5-turbo"
model = "gpt-3.5-turbo"
# Change the base_url if you are using a different OpenAI-compatible API
base_url = "https://api.openai.com"
```

Once enabled, you can use AI completion by pressing `Ctrl/Cmd-Shift-e` in a
cell. This will open an input to modify the cell using AI.

<div align="center">
<figure>
<video src="/_static/ai-completion.mp4" controls="controls" width="100%" height="100%"></video>
<figcaption>Use AI to modify a cell by pressing `Ctrl/Cmd-Shift-e`.</figcaption>
</figure>
</div>

### Using other AI providers

marimo supports OpenAI's GPT-3.5 API by default. If your provider is compatible with OpenAI's API, you can use it by changing the `base_url` in the configuration.

For other providers not compatible with OpenAI's API, please submit a [feature request](https://github.com/marimo-team/marimo/issues) or "thumbs up" an existing one.

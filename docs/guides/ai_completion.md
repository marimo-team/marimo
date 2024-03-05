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

1. You need add the following to your `~/.marimo.toml`:

```toml
[experimental]
ai = true
```

2. Add your OpenAI API key to your environment:

```bash
export OPENAI_API_KEY=your-api-key
```

Once enabled, you can use AI completion by pressing `Ctrl/Cmd-Shift-e` in a cell. This will open an input to modify the cell using AI.

<div align="center">
<figure>
<video src="/_static/ai-completion.mp4" controls="controls" width="100%" height="100%"></video>
<figcaption>Use AI to modify a cell by pressing `Ctrl/Cmd-Shift-e`.</figcaption>
</figure>
</div>

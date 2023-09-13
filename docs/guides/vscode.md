# VS Code integration

marimo can be run directly from VS Code. This is useful for launching marimo directly from the editor.

Just install the [marimo VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo) and you're good to go!

<div align="center">
<figure>
<img src="/_static/vscode-marimo.png"/>
</figure>
</div>

## Features

- 🚀 Launch marimo from VS Code, in both "edit mode" and "run mode".
- 💻 View the terminal output of marimo directly in VS Code.
- 🌐 View the marimo browser window directly in VS Code or in your default browser.

## Known Issues

VS Code's embedded browser does not support all native browser features. If you encounter any issues, try opening marimo in your default browser instead.
For example, the embedded browser will not support PDF render, audio recording, or video recording.

## Extension Settings

You can configure the extension using the following settings:

- `marimo.browserType`: Browser to open marimo app (`system` or `embedded`, default: `embedded`)
- `marimo.port`: Default port for marimo server (default: `2718`)
- `marimo.showTerminal`: Open the terminal when the server starts (default: `false`)

## Repository

The source code for the marimo VS Code extension is available on [GitHub](https://github.com/marimo-team/vscode-marimo).

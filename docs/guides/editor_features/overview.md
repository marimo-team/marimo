# Editor overview

This guide introduces some of marimo editor's features, including
a variables panel, dependency graph viewer, table of contents, HTML export,
GitHub copilot, code formatting, a feedback form, and more.

## Configuration

The editor exposes of a number of settings for the current notebook,
as well as user-wide configuration that will apply to all your notebooks.
These settings include the option to display the current notebook in
full width, to use vim keybindings, to enable GitHub copilot, and more.

To access these settings, click the gear icon in the top-right of the editor:

<div align="center">
<img src="/_static/docs-user-config.png"  />
</div>

A non-exhaustive list of settings:

- Outputs above or below code cells
- [Disable/enable autorun](/guides/reactivity.md#runtime-configuration)
- Package installation
- Vim keybindings
- Dark mode
- Auto-save
- Auto-complete
- Editor font-size
- Code formatting with ruff/black
- [GitHub Copilot](/guides/editor_features/ai_completion.md)
- [LLM coding assistant](/guides/editor_features/ai_completion.md)
- [Module autoreloading](/guides/configuration/runtime_configuration.md#on-module-change)

### Vim keybindings

marimo supports vim keybindings.

**Additional bindings/features:**

- `gd` - go to definition
- `dd` - when a cell is empty, delete it

## Overview panels

marimo ships with the IDE panels that provide an overview of your notebook

- **file explorer**: view the file tree, open other notebooks
- **variables**: explore variable values, see where they are defined and used, with go-to-definition
- **data explorer**: see dataframe and table schemas at a glance
- **dependency graph**: view dependencies between cells, drill-down on nodes and edges
- **package manager**: add and remove packages, and view your current environment
- **table of contents**: corresponding to your markdown
- **documentation** - move your text cursor over a symbol to see its documentation
- **logs**: a continuous stream of stdout and stderr
- **scratchpad**: a scratchpad cell where you can execute throwaway code
- **snippets** - searchable snippets to copy directly into your notebook
- **feedback** - share feedback!

These panels can be toggled via the buttons in the left of the editor.

## Cell actions

Click the three dots in the top right of a cell to pull up a context menu,
letting you format code, hide code, send a cell to the top or bottom of the
notebook, give the cell a name, and more.

Drag a cell using the vertical dots to the right of the cell.

## Right-click menus

marimo supports context-sensitive right-click menus in various locations of
the editor. Right-click on a cell to open a context-sensitive menu; right click
on the create-cell button (the plus icon) to get options for the cell type to
create.

## Go-to-definition

- Click on a variable in the editor to see where it's defined and used
- `Cmd/Ctrl-Click` on a variable to jump to its definition
- Right-click on a variable to see a context menu with options to jump to its definition

## Keyboard shortcuts

We've kept some well-known [keyboard
shortcuts](/guides/editor_features/hotkeys.md) for notebooks (`Ctrl-Enter`,
`Shift-Enter`), dropped others, and added a few of our own. Hit
`Ctrl/Cmd-Shift-H` to pull up the shortcuts.

We know keyboard shortcuts are very personal; you can remap them in the
configuration.

_Missing a shortcut? File a
[GitHub issue](https://github.com/marimo-team/marimo/issues)._

## Command palette

Hit `Cmd/Ctrl+K` to open the command palette.

<div align="center">
<figure>
<img src="/_static/docs-command-palette.png"/>
<figcaption>Quickly access common commands with the command palette.</figcaption>
</figure>
</div>

_Missing a command? File a
[GitHub issue](https://github.com/marimo-team/marimo/issues)._

## Share on our online playground

Get a link to share your notebook via our [online playground](/guides/wasm.md):

<div align="center">
<figure>
<img src="/_static/share-wasm-link.gif"/>
</figure>
</div>

_Our online playground uses WebAssembly. Most but not all packages on PyPI
are supported. Local files are not synchronized to our playground._

## Export to static HTML

Export the current view your notebook to static HTML via the notebook
menu:

<div align="center">
<figure>
<img src="/_static/docs-html-export.png"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>

You can also export to HTML at the command-line:

```bash
marimo export html notebook.py -o notebook.html
```

## Send feedback

The question mark icon in the panel tray opens a
dialog to send anonymous feedback. We welcome any and all feedback, from the
tiniest quibbles to the biggest blue-sky dreams.

<div align="center">
<figure>
<img src="/_static/docs-feedback-form.png"/>
<figcaption>Send anonymous feedback with our feedback form.</figcaption>
</figure>
</div>

If you'd like your feedback to start a conversation (we'd love to talk with
you!), please consider posting in our [GitHub
issues](https://github.com/marimo-team/marimo/issues) or
[Discord](https://marimo.io/discord?ref=docs). But if you're in a flow state and
can't context switch out, the feedback form has your back.

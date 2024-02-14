# Editor features

This guide introduces some of marimo editor's features, including
a variables panel, dependency graph viewer, table of contents, HTML export,
GitHub copilot, code formatting, HTML export, a feedback form, and more.

This guide introduces some of these features.

## Settings

The editor exposes of a number of settings for the current notebook,
as well as user-wide configuration that will apply to all your notebooks.
These settings include the option to display the current notebook in
full width, to use vim keybindings, to enable GitHub copilot, and more.

To access these settings, click the gear icon in the top-right of the editor.

<div align="center">
<figure>
<img src="/_static/docs-settings.png"/>
<figcaption>Click the gear icon to access notebook and editor settings.</figcaption>
</figure>
</div>


## Overview panels

marimo ships with the following IDE-like panels that help provide an overview
of your notebook:

1. **errors**: view errors in each cell;
2. **variables**: explore variable values, see where they are defined and used;
3. **dependency graph**: view dependencies between cells;
4. **table of contents**: corresponding to your markdown;
5. **logs**: a continuous stream of stdout and stderr.

<div align="center">
<figure>
<img src="/_static/docs-panel-icons.png"/>
<figcaption>Click these buttons to access the editor panels.</figcaption>
</figure>
</div>

These panels can be toggled via the buttons in the lower left of the editor.

## Cell actions

Click the dot array to the right of a cell to pull up a context menu (or hold
and drag to move the cell):

<div align="center">
<figure>
<img src="/_static/docs-cell-actions.png"/>
<figcaption>Access cell actions like code formatting, hiding code, and more
through the cell context menu.</figcaption>
</figure>
</div>

## Keyboard shortcuts

We've kept some well-known keyboard shortcuts for notebooks (`Ctrl-Enter`,
`Shift-Enter`), dropped others, and added a few of our own. Hit
`Ctrl/Cmd-Shift-H` to pull up the shortcuts.

We know keyboard shortcuts are very personal; we'll let you remap them in the
future.

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

## Export to static HTML

Export the current view your notebook to static HTML via the notebook
menu:

<div align="center">
<figure>
<img src="/_static/docs-html-export.png"/>
<figcaption>Download as static HTML.</figcaption>
</figure>
</div>

## Configuration

Click the settings icon in the top right to access important configuration
settings. For example, you can configure marimo to not autorun on startup.
You can also enable GitHub Copilot from this menu.

<div align="center">
<figure>
<img src="/_static/docs-user-config.png"/>
<figcaption>Configure settings.</figcaption>
</figure>
</div>

A non-exhausted list of settings (for searchability):

- Vim keymaps
- Dark mode
- Auto-save
- Auto-complete
- Editor font-size
- Formatting rules
- GitHub Copilot

## Send feedback

The question mark icon in the panels tray (lower left of the editor) opens a
dialog to send anonymous feedback. We welcome any and all feedback, from the
tiniest quibbles to the biggest blue sky dreams.

<div align="center">
<figure>
<img src="/_static/docs-feedback-form.png"/>
<figcaption>Send anonymous feedback with our feedback form.</figcaption>
</figure>
</div>

If you'd like your feedback to start a conversation (we'd love to talk with
you!), please consider posting in our [GitHub
issues](https://github.com/marimo-team/marimo/issues) or
[Discord](https://discord.gg/JE7nhX6mD8). But if you're in a flow state and
can't context switch out, the feedback form has your back.

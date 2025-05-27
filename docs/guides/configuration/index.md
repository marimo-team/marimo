# Configuration

marimo offers two types of configuration: User Configuration and App
Configuration. Both can be easily managed through the Settings menu in the
marimo editor.

<img align="right" src="/_static/docs-app-config.png" width="300px"/>

## App Configuration

App Configuration is specific to each notebook and is stored in the `notebook.py` file. This allows you to customize various aspects of your notebook, including:

- Notebook width
- Notebook title
- [Custom CSS](theming.md)
- [Custom HTML Head](html_head.md)
- Automatically download HTML snapshots

Configure these settings through the notebook menu (⚙️) in the top-right corner.

<br clear="left"/>

## User Configuration

User Configuration applies globally across all marimo notebooks and is stored
in a `$XDG_CONFIG_HOME/marimo/marimo.toml` file.

While you can edit the `$XDG_CONFIG_HOME/marimo/marimo.toml` file directly, we recommend using the
marimo UI for a more user-friendly experience.

<video controls width="100%" height="100%" align="center" src="/_static/docs-user-config.mp4"> </video>

You can customize the following settings:

- [Runtime](runtime_configuration.md), including whether notebooks autorun
- [Hotkeys](../editor_features/hotkeys.md)
- Completion (auto-completion, AI copilot, etc.)
- Display (theme, font size, output placement, etc.)
- Autosave
- [Package management](../editor_features/package_management.md#package-management)
- Server settings
- [VIM keybindings](../editor_features/overview.md#vim-keybindings)
- Formatting settings
- [AI assistance](../editor_features/ai_completion.md)
- [Snippets](snippets.md)
- Experimental features

### User configuration file

marimo searches for the `.marimo.toml` file in the following order:

1. Current directory
2. Parent directories (moving up the tree)
3. Home directory (`~/.marimo.toml`)
4. [XDG](https://xdgbasedirectoryspecification.com/) directory (`~/.config/marimo/marimo.toml` or `$XDG_CONFIG_HOME/marimo/marimo.toml`)

If no `.marimo.toml` file is found, marimo creates one for you in an XDG config
compliant way.

To view your current configuration and locate the config file, run:

```bash
marimo config show
```

To describe the user configuration options, run:

```bash
marimo config describe
```

### Overriding settings with pyproject.toml

You can override user configuration settings with a `pyproject.toml` file. This
is useful for sharing configurations across teams or ensuring consistency across
notebooks. You must edit the `pyproject.toml` file directly to override settings.

For example, the following `pyproject.toml` file overrides the `autosave` setting
in the user configuration:

```toml title="pyproject.toml"
[tool.marimo.formatting]
line_length = 120

[tool.marimo.display]
default_width = "full"

[tool.marimo.runtime]
default_sql_output = "native"
```

You can override any user configuration setting in this way. To find these settings run `marimo config show`.

!!! note "Overridden settings"
    Settings overridden in `pyproject.toml` or script metadata cannot be changed through the marimo editor's settings menu. Any changes made to overridden settings in the editor will not take effect.

### Script Metadata Configuration

You can also configure marimo settings directly in your notebook files using script metadata (PEP 723). Add a `script` block at the top of your notebook:

```python
# /// script
# [tool.marimo.runtime]
# auto_instantiate = false
# on_cell_change = "lazy"
# [tool.marimo.display]
# theme = "dark"
# cell_output = "below"
# ///
```

!!! note "Configuration precedence"
    Script metadata configuration has the highest precedence, followed by `pyproject.toml` configuration, then user configuration:

    **Script config > pyproject.toml config > user config**

## Environment Variables

marimo supports the following environment variables for advanced configuration:

| Environment Variable          | Description                                                                                                                  | Default Value   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `MARIMO_OUTPUT_MAX_BYTES` (deprecated, use `pyproject.toml`)     | Maximum size of output that marimo will display. Outputs larger than this will be truncated.                                 | 8,000,000 (8MB) |
| `MARIMO_STD_STREAM_MAX_BYTES` (deprecated, use `pyproject.toml`) | Maximum size of standard stream (stdout/stderr) output that marimo will display. Outputs larger than this will be truncated. | 1,000,000 (1MB) |
| `MARIMO_SKIP_UPDATE_CHECK`    | If set to "1", marimo will skip checking for updates when starting.                                                          | Not set         |
| `MARIMO_SQL_DEFAULT_LIMIT`    | Default limit for SQL query results. If not set, no limit is applied.                                                        | Not set         |

### Tips

- The `.marimo.toml` file can be version controlled to share configurations across teams
- App configurations can be committed with notebooks to ensure consistent appearance

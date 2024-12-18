# Configuration

marimo offers two types of configuration: User Configuration and App
Configuration. Both can be easily managed through the Settings menu in the
marimo editor.

<img align="right" src="/_static/docs-app-config.png" width="300px"/>

## App Configuration

App Configuration is specific to each notebook and is stored in the `notebook.py` file. This allows you to customize various aspects of your notebook, including:

- Notebook width
- Notebook title
- [Custom CSS](../guides/configuration/theming.md)
- [Custom HTML Head](../guides/configuration/html_head.md)
- Automatically download HTML snapshots

Configure these settings through the notebook menu (⚙️) in the top-right corner.

<br clear="left"/>

## User Configuration

User Configuration applies globally across all marimo notebooks and is stored
in a `.marimo.toml` file.

While you can edit the `.marimo.toml` file directly, we recommend using the
marimo UI for a more user-friendly experience.

<video controls width="100%" height="100%" align="center" src="/_static/docs-user-config.mp4"> </video>

You can customize the following settings:

- [Runtime](../guides/configuration/runtime_configuration.md), including whether notebooks autorun
- [Hotkeys](../guides/editor_features/hotkeys.md)
- Completion (auto-completion, AI copilot, etc.)
- Display (theme, font size, output placement, etc.)
- Autosave
- [Package management](../guides/editor_features/package_management.md#package-management)
- Server settings
- [VIM keybindings](../guides/editor_features/overview.md#vim-keybindings)
- Formatting settings
- [AI assistance](../guides/editor_features/ai_completion.md)
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

```toml
[tool.marimo.format]
line_length = 120

[tool.marimo.display]
default_width = "full"
```

You can override any user configuration setting in this way. To find these settings run `marimo config show`.

## Environment Variables

marimo supports the following environment variables for advanced configuration:

| Environment Variable          | Description                                                                                                                  | Default Value   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `MARIMO_OUTPUT_MAX_BYTES`     | Maximum size of output that marimo will display. Outputs larger than this will be truncated.                                 | 5,000,000 (5MB) |
| `MARIMO_STD_STREAM_MAX_BYTES` | Maximum size of standard stream (stdout/stderr) output that marimo will display. Outputs larger than this will be truncated. | 1,000,000 (1MB) |
| `MARIMO_SKIP_UPDATE_CHECK`    | If set to "1", marimo will skip checking for updates when starting.                                                          | Not set         |
| `MARIMO_SQL_DEFAULT_LIMIT`    | Default limit for SQL query results. If not set, no limit is applied.                                                        | Not set         |

### Tips

- The `.marimo.toml` file can be version controlled to share configurations across teams
- App configurations can be committed with notebooks to ensure consistent appearance

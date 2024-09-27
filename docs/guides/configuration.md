# Configuration

marimo offers two types of configuration: User Configuration and App Configuration. Both can be easily managed through the Settings menu in the marimo editor.

## App Configuration

App Configuration is specific to each notebook and is stored in the `notebook.py` file. This allows you to customize various aspects of your notebook, including:

- Notebook width
- Notebook title
- Custom CSS
- Additional app-specific settings
- _and more_

## User Configuration

User Configuration applies globally across all marimo notebooks and is stored in a `.marimo.toml` file. marimo searches for this file in the following order:

1. Current directory
2. Parent directories (moving up the tree)
3. Home directory (`~/.marimo.toml`)
4. [XDG](https://xdgbasedirectoryspecification.com/) directory (`~/.config/marimo/marimo.toml` or `$XDG_CONFIG_HOME/marimo/marimo.toml`)

If no `.marimo.toml` file is found, marimo creates a default one in your home directory.

While you can edit the `.marimo.toml` file directly, we recommend using the marimo UI for a more user-friendly experience. To view your current configuration and locate the config file, run:

```bash
marimo config show
```

You can customize:

- [Runtime configuration](/guides/runtime_configuration.md)
- [Hotkeys](/guides/editor_features/hotkeys.md)
- Completion settings (auto-completion, AI copilot, etc.)
- Display settings (theme, font size, output placement, etc.)
- Autosave settings
- Package management preferences
- Server settings
- VIM keybindings
- Formatting settings
- [AI settings](/guides/editor_features/ai_completion.md)
- _and more_

## Environment Variables

There are some configuration options that can be set via environment variables. These are:

| Environment Variable          | Description                                                                                                                  | Default Value   |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `MARIMO_OUTPUT_MAX_BYTES`     | Maximum size of output that marimo will display. Outputs larger than this will be truncated.                                 | 5,000,000 (5MB) |
| `MARIMO_STD_STREAM_MAX_BYTES` | Maximum size of standard stream (stdout/stderr) output that marimo will display. Outputs larger than this will be truncated. | 1,000,000 (1MB) |
| `MARIMO_SKIP_UPDATE_CHECK`    | If set to "1", marimo will skip checking for updates when starting.                                                          | Not set         |
| `MARIMO_SQL_DEFAULT_LIMIT`    | Default limit for SQL query results. If not set, no limit is applied.                                                        | Not set         |

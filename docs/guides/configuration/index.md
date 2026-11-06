# Configuration
marimo’s editor, runtime, and server can be configured through user settings, project files, notebook metadata, and environment variables. This page explains how to find available options, set their values, and determine which source takes priority.

## Configuration options

For available options, descriptions, types, and defaults, run:

```bash
marimo config describe
```

For guidance on specific configuration options, see [runtime configuration](runtime_configuration.md),
[AI assistance](../editor_features/ai_completion.md), and
[theming](theming.md).

To view the configuration values being used:

```bash
marimo config show
```

Pass a notebook path to include its project settings and script metadata:

```bash
marimo config show notebook.py
```


## Ways to set configurations

marimo applies each configuration value individually from the configuration sources listed below.

The configuration sources are listed below **in order, from lowest to highest priority**.

1. <a id="user-configuration-file"></a><a id="user-settings"></a>**User configuration file `.marimo.toml`**

    The **User settings** UI edits the **first existing file** in this search order:

    1. `.marimo.toml` in the current working directory
    2. `.marimo.toml` in parent directories, stopping at your home directory if it
       is an ancestor, or at the filesystem root otherwise
    3. `~/.marimo.toml`
    4. `$XDG_CONFIG_HOME/marimo/marimo.toml`, defaulting to
       `~/.config/marimo/marimo.toml`

    If none exists, marimo creates its user configuration file at the XDG location.

    You can also edit the TOML file
    directly:

    ```toml title=".marimo.toml"
    [display]
    theme = "dark"
    ```

2. <a id="overriding-settings-with-pyprojecttoml"></a>**Per-project configuration in `pyproject.toml`**

    Use `[tool.marimo]` sections in the nearest `pyproject.toml` to share settings
    across a project. marimo searches upward from the notebook, or from the working
    directory when no notebook is specified.

    For a file-browser configuration example, see [additional file browser roots](../editor_features/panels.md#additional-file-browser-roots).

3. <a id="script-metadata-configuration"></a>**Script metadata configuration in notebook**

    Put configuration in a [PEP 723](https://peps.python.org/pep-0723/) script block
    at the top of a notebook to override project and user settings for that notebook:

    ```python
    # /// script
    # [tool.marimo.display]
    # theme = "dark"
    # ///
    ```

    Changes require a server restart. Script metadata supports a subset of options:
    settings that access credentials or external services, such as the `ai`, `mcp`,
    `completion`, `secrets`, and `server` sections, are ignored. It also ignores
    `runtime.auto_instantiate`, `experimental.isolate_apps`, and `display.custom_css`.

4. <a id="environment-variables"></a>**Environment variables**

    Environment variables are named following the pattern `MARIMO_<CATEGORY>_<NAME>`:

    ```bash
    export MARIMO_DISPLAY_THEME=dark
    export MARIMO_RUNTIME_PYTHONPATH='["src", "lib"]'
    export MARIMO_KEYMAP_OVERRIDES='{"run-cell": "Shift-Enter"}'
    ```

    <a id="dotenv-files"></a>
    **Dotenv files** supply environment variables to notebook code when the
    runtime starts, after startup configuration has been resolved. They do not
    form another layer in this hierarchy. Existing environment variables take
    precedence over values in these files.

    By default, marimo loads `.env` beside the nearest `pyproject.toml`, or beside
    the notebook when there is no project. Automatic discovery skips the home
    directory unless it contains the project's `pyproject.toml`. Set
    `runtime.dotenv` to choose different files; see
    [dotenv loading](runtime_configuration.md#env-files) for examples and run
    `marimo config describe` for path resolution rules.

To identify which source was used to set each config value, use:
```bash
marimo config show --show-sources
```

### Restrictions and overrides

CLI flags such as `--skip-update-check` take precedence over the corresponding
environment variable. Administrator restrictions such as `MARIMO_RESTRICT_SHARING` are always
enforced, regardless of other sources.

Settings supplied by `pyproject.toml`, script metadata, or environment variables
cannot be overridden through the editor's User settings menu. Server session
cookie settings take effect when the server starts.

!!! note "Trusted configuration"
    `signing`, `cache.verification`, `cache.loader`, and `server.session_secret`
    are read only from trusted user configuration (`~/.marimo.toml` or the XDG
    file) or environment variables. They are ignored in project files, script
    metadata, and workspace `.marimo.toml` files. Workspace `.marimo.toml` files
    also cannot set `cache.store`. See [project file security](../../security.md#project-files)
    and [cache signing and trust](../../api/caching.md#cache-signing-and-trust).

## Notebook settings

Some notebook-specific settings, such as title, width, [custom CSS](theming.md),
[HTML head](html_head.md), and automatic exports, are managed separately from the rest of marimo's configuration. These notebook-specific settings are stored in the notebook's `marimo.App(...)` Open the notebook menu (⚙️) in the top-right corner of the marimo editor to change them.

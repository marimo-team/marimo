# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, cast

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    CompletionConfig,
    ExperimentalConfigType,
    ExportType,
    LanguageServersConfig,
    MarimoConfig,
    PartialMarimoConfig,
    RuntimeConfig,
    SharingConfig,
    SqlOutputType,
    Theme,
    WidthType,
    merge_config,
    merge_default_config,
)
from marimo._config.packages import PackageManagerKind
from marimo._config.reader import (
    ALLOWED_SCRIPT_CONFIG_TOP_KEYS,
    allowlist_script_config,
    find_nearest_pyproject_toml,
    get_marimo_config_from_pyproject_dict,
    read_marimo_config,
    read_pyproject_marimo_config,
    sanitize_pyproject_dict,
    strip_untrusted_config,
)
from marimo._config.secrets import (
    mask_secrets,
    mask_secrets_partial,
    remove_secret_placeholders,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.source import ConfigReader, ConfigStore
from marimo._config.utils import (
    get_or_create_user_config_path,
    is_trusted_user_config_path,
)
from marimo._utils.env import env_to_value

LOGGER = _loggers.marimo_logger()


def get_default_config_manager(
    *, current_path: str | None
) -> MarimoConfigManager:
    """
    Get the default config manager

    Args:
        current_path: The current path of the notebook, or a directory.
        If the current path is a notebook, the config manager will read the
        project configuration from the notebook following PEP 723.
    """
    # Current path should be the notebook file
    # If it's not known, use the current working directory
    if current_path is None:
        current_path = os.getcwd()

    return MarimoConfigManager(
        UserConfigStore(),
        PyprojectConfigReader(current_path),
        ScriptConfigReader(current_path),
        EnvConfigReader(),
        # Always merged last; see SecurityConfigReader.
        SecurityConfigReader(),
    )


class ConfigResolver:
    """Resolve defaults and ordered reader values without persisting settings.

    Later readers override earlier readers, with security enforcement always
    applied last. Built-in defaults are defined in `config.py`; project and
    script readers supply the contextual dotenv defaults.
    """

    def __init__(self, *readers: ConfigReader) -> None:
        # Machine-wide enforcement remains above every ordinary reader.
        self.readers = tuple(
            reader
            for reader in readers
            if not isinstance(reader, SecurityConfigReader)
        ) + tuple(
            reader
            for reader in readers
            if isinstance(reader, SecurityConfigReader)
        )

    def get_config_defaults(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get dotenv defaults beneath explicit configuration settings."""
        result: MarimoConfig = cast(MarimoConfig, {})
        for reader in self.readers:
            if isinstance(reader, (PyprojectConfigReader, ScriptConfigReader)):
                result = merge_config(
                    result, reader.get_defaults(hide_secrets=hide_secrets)
                )
        return cast(PartialMarimoConfig, result)

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Resolve defaults and all readers in order, including the user reader."""
        result = merge_default_config(
            self.get_config_defaults(hide_secrets=hide_secrets)
        )
        for reader in self.readers:
            result = merge_config(
                result, reader.read(hide_secrets=hide_secrets)
            )
        return result

    # Convenience methods for common access patterns

    @cached_property
    def _config(self) -> MarimoConfig:
        return self.get_config()

    @property
    def default_width(self) -> WidthType:
        return self._config["display"]["default_width"]

    @property
    def default_auto_download(self) -> list[ExportType]:
        return self._config["runtime"].get("default_auto_download", [])

    @property
    def default_sql_output(self) -> SqlOutputType:
        return self._config["runtime"]["default_sql_output"]

    @property
    def theme(self) -> Theme:
        return self._config["display"]["theme"]

    @property
    def package_manager(self) -> PackageManagerKind:
        return self._config["package_management"]["manager"]

    @property
    def completion(self) -> CompletionConfig:
        return self._config["completion"]

    @property
    def language_servers(self) -> LanguageServersConfig:
        if "language_servers" in self._config:
            return self._config["language_servers"]
        return {}

    @property
    def is_auto_save_enabled(self) -> bool:
        return self._config["save"]["autosave"] == "after_delay"

    @property
    def experimental(self) -> ExperimentalConfigType:
        if "experimental" in self._config:
            return self._config["experimental"]
        return {}


class MarimoConfigManager:
    """Coordinate resolved configuration access and user persistence.

    Reads delegate to `resolver`; saves delegate to the user store. Notebook
    settings stored in `marimo.App(...)` use a separate schema.
    """

    def __init__(self, *readers: ConfigReader) -> None:
        self.resolver = ConfigResolver(*readers)

    @property
    def readers(self) -> tuple[ConfigReader, ...]:
        return self.resolver.readers

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        return self.resolver.get_config(hide_secrets=hide_secrets)

    @property
    def user_config_mgr(self) -> UserConfigStore:
        """Locate the user store for user configuration reads and saves."""
        for reader in self.readers:
            if isinstance(reader, UserConfigStore):
                return reader
        raise ValueError("No user configuration store is configured")

    def get_user_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the user configuration with built-in defaults."""
        return self.user_config_mgr.get_config(hide_secrets=hide_secrets)

    def get_config_overrides(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get the configuration overrides

        Security partials are merged last, so the enforcements they apply
        cannot be overridden by any other config reader.
        """
        override_readers = tuple(
            reader
            for reader in self.readers
            if not isinstance(reader, UserConfigStore)
        )
        if not override_readers:
            return {}
        if len(override_readers) == 1:
            return cast(
                PartialMarimoConfig,
                override_readers[0].read(hide_secrets=hide_secrets),
            )
        result: MarimoConfig = cast(MarimoConfig, {})
        for reader in override_readers:
            result = merge_config(
                result, reader.read(hide_secrets=hide_secrets)
            )
        return cast(PartialMarimoConfig, result)

    def save_config(
        self, config: MarimoConfig | PartialMarimoConfig
    ) -> MarimoConfig:
        """Save the configuration"""
        return self.user_config_mgr.save_config(config)

    def with_overrides(
        self, overrides: PartialMarimoConfig
    ) -> MarimoConfigManager:
        """Get a new config manager with the given overrides

        The new override is appended after the existing partials but before the
        security partials, which the constructor keeps last so they always win.
        """
        return self.with_reader(InMemoryConfigReader(overrides))

    def with_reader(self, reader: ConfigReader) -> MarimoConfigManager:
        """Get a new config manager with the given reader layered on.

        Unlike `with_overrides`, the reader keeps answering `hide_secrets`
        itself, so a masked read does not become the value an unmasked read
        returns.
        """
        return MarimoConfigManager(*self.readers, reader)


class PyprojectConfigReader(ConfigReader):
    """Read shared marimo settings from the nearest `pyproject.toml`.

    Searches upward from a notebook or directory and reads `[tool.marimo]`.
    In the default hierarchy these settings override user settings and are
    overridden by script metadata. File paths are resolved against the project
    directory, and cache-signing trust settings are excluded.

    This read-only source configures marimo, not `marimo.App(...)` settings.
    Missing configuration contributes no values. Reads are cached; file edits
    require a server restart to take effect.
    """

    def __init__(self, start_path: str) -> None:
        self.start_path = start_path
        self.pyproject_path = find_nearest_pyproject_toml(start_path)

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        return self.get_config(hide_secrets=hide_secrets)

    @property
    def _dotenv_root(self) -> Path:
        """Directory that relative `dotenv` paths resolve against.

        Standalone notebooks (such as sandboxed ones) have no
        pyproject.toml to anchor on, so they fall back to the directory
        holding the notebook.
        """
        if self.pyproject_path is not None:
            return self.pyproject_path.parent
        start_path = Path(self.start_path)
        return start_path if start_path.is_dir() else start_path.parent

    def get_defaults(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get the `.env` next to the project, loaded when no layer set `dotenv`"""
        root = self._dotenv_root
        if self.pyproject_path is None and _is_home_directory(root):
            # NB. Without a pyproject.toml the anchor is wherever the notebook
            # or `marimo edit` sits. For ~ that would load ~/.env and list its
            # keys in the secrets panel, so the default is skipped there.
            return {}
        # NB. Emitted as a default, not from get_config(): get_config() is an
        # override layer over the user configuration, so a path nobody wrote
        # would outrank the user's own runtime.dotenv and would show up as a
        # project override in the settings editor.
        defaults = cast(
            PartialMarimoConfig,
            {"runtime": {"dotenv": [str((root / ".env").absolute())]}},
        )
        if hide_secrets:
            return mask_secrets_partial(defaults)
        return defaults

    # It is safe to cache this config, as we only read from the pyproject.toml
    # and never update it. If the user updates the pyproject.toml,
    # it is ok to expect updates to be reflected after a server restart.
    @lru_cache(maxsize=2)  # noqa: B019
    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        try:
            project_config = (
                read_pyproject_marimo_config(self.pyproject_path)
                if self.pyproject_path is not None
                else None
            )
            if project_config is None:
                return {}
            project_config = self._resolve_pythonpath(project_config)
            project_config = self._resolve_dotenv(project_config)
            project_config = self._resolve_custom_css(project_config)
            project_config = self._resolve_vimrc(project_config)
            # pyproject.toml is honoured as written apart from trust anchors.
            # Opening a notebook inside a project already means trusting that
            # project, so an allowlist here adds little protection.
            project_config = strip_untrusted_config(project_config)
        except Exception as e:
            LOGGER.warning("Failed to read project config: %s", e)
            return {}

        if hide_secrets:
            return mask_secrets_partial(project_config)
        return project_config

    def _resolve_pythonpath(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        if self.pyproject_path is None:
            return config

        if "runtime" not in config:
            return config

        if "pythonpath" not in config["runtime"]:
            return config

        pythonpath = config["runtime"]["pythonpath"]

        if not isinstance(pythonpath, list):
            return config

        resolved_pythonpath = [
            str((self.pyproject_path.parent / path).absolute())
            for path in pythonpath
        ]
        return {
            **config,
            "runtime": {
                **config["runtime"],
                "pythonpath": resolved_pythonpath,
            },
        }

    def _resolve_dotenv(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        runtime = config.get("runtime", cast(RuntimeConfig, {}))
        if "dotenv" not in runtime:
            # NB. The default is emitted by get_defaults() instead, which
            # ranks below the user configuration.
            return config
        dotenv = runtime["dotenv"]

        if not isinstance(dotenv, list):
            return config

        root = self._dotenv_root
        resolved_dotenv = [str((root / path).absolute()) for path in dotenv]
        return {**config, "runtime": {**runtime, "dotenv": resolved_dotenv}}

    def _resolve_custom_css(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        if self.pyproject_path is None:
            return config

        if "display" not in config:
            return config

        display = config["display"]
        custom_css = display.get("custom_css", [])

        if not isinstance(custom_css, list):
            return config

        resolved_custom_css: list[str] = []
        for path in custom_css:
            try:
                expanded_path = Path(path).expanduser()
            except RuntimeError as e:
                LOGGER.warning(
                    "Failed to resolve custom CSS file %s: %s", path, e
                )
                continue
            resolved_custom_css.append(
                str((self.pyproject_path.parent / expanded_path).absolute())
            )
        return {
            **config,
            "display": {**display, "custom_css": resolved_custom_css},
        }

    def _resolve_vimrc(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        if self.pyproject_path is None:
            return config

        if "keymap" not in config:
            return config

        keymap = config["keymap"]
        vimrc = keymap.get("vimrc")

        if not isinstance(vimrc, str):
            return config

        resolved_vimrc = str((self.pyproject_path.parent / vimrc).absolute())
        return {
            **config,
            "keymap": {**keymap, "vimrc": resolved_vimrc},
        }


class EnvConfigReader(ConfigReader):
    """Read supported marimo settings from the process environment.

    Maps an explicit set of environment variables to configuration keys;
    general `MARIMO_*` configuration parsing is not yet supported. The default
    hierarchy applies these values after user, project, and script settings.

    This read-only source reads the environment on each call. It does not load
    the `.env` files selected by `runtime.dotenv`; the notebook runtime does.
    """

    def _maybe_override_from_env(
        self,
        key: str,
        path: list[str],
        config: PartialMarimoConfig,
        allowed_values: tuple[Any, ...] | None = None,
    ) -> None:
        loaded_value = env_to_value(key)
        if not isinstance(loaded_value, tuple):
            return
        value = loaded_value[0]
        if allowed_values is not None and value not in allowed_values:
            LOGGER.warning(
                "Ignoring invalid value %r for %s; expected one of %s",
                value,
                key,
                ", ".join(map(repr, allowed_values)),
            )
            return

        current = cast(dict[str, Any], config)
        for p in path[:-1]:
            if p not in current or not isinstance(current[p], dict):
                current[p] = {}
            current = current[p]
        current[path[-1]] = value
        return

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        return self.get_config(hide_secrets=hide_secrets)

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        """Get the configuration, as a partial configuration"""
        project_config: PartialMarimoConfig = {}
        # We could do this dynamically, but list explicitly for now to reduce
        # surface area
        self._maybe_override_from_env(
            "_MARIMO_CONFIG_OVERLOAD_RUNTIME_AUTO_INSTANTIATE",
            ["runtime", "auto_instantiate"],
            project_config,
        )
        self._maybe_override_from_env(
            "MARIMO_SERVER_TRANSPORT",
            ["server", "transport"],
            project_config,
            allowed_values=("websocket", "sse"),
        )
        if hide_secrets:
            return mask_secrets_partial(project_config)
        return project_config


class SecurityConfigReader(ConfigReader):
    """Machine-wide security enforcements that always take precedence.

    `MarimoConfigManager` merges partials of this type last, after every other
    config source (including any added by `with_overrides()`), so the
    enforcements they apply cannot be re-enabled by a user, project, script,
    env, or runtime override. Intended for restrictions set by infra admins
    outside the user's control, e.g. in a devpod or container spec.

    This read-only source uses `GLOBAL_SETTINGS`, rather than parsing arbitrary
    environment variables. Today it handles `MARIMO_RESTRICT_SHARING`, hiding
    external sharing affordances. This is a UI policy, not an access-control
    boundary for exported code or server endpoints.
    """

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        return self.get_config(hide_secrets=hide_secrets)

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        del hide_secrets  # no secrets are produced here
        config: PartialMarimoConfig = {}
        if GLOBAL_SETTINGS.RESTRICT_SHARING:
            # Hide every external code-sharing affordance (shareable WASM
            # links, molab, HTML publishing) across all notebook sessions.
            # See GLOBAL_SETTINGS.RESTRICT_SHARING. Derive the keys from the
            # schema so any future sharing target is disabled automatically;
            # every key in SharingConfig is a boolean that hides the affordance
            # when False.
            config["sharing"] = cast(
                SharingConfig,
                dict.fromkeys(SharingConfig.__annotations__, False),
            )
        return config


class ScriptConfigReader(ConfigReader):
    """Read the script configuration following PEP 723

    This looks like a pyproject.toml serialized as a comment in the header
    of the script.
    """

    def __init__(self, filename: str | None) -> None:
        self.filename = filename

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        return self.get_config(hide_secrets=hide_secrets)

    def get_defaults(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get the `.env` next to the notebook, loaded when no layer set `dotenv`"""
        # NB. In a directory workspace the project manager anchors on the
        # directory marimo edit opened, not on the notebook a session runs.
        # Script config already outranks project config, so the notebook's
        # default outranks the workspace's the same way.
        if self.filename is None:
            return {}
        return PyprojectConfigReader(self.filename).get_defaults(
            hide_secrets=hide_secrets
        )

    # It is safe to cache this config, as we only read from the script
    # and never update it. If the user updates the script,
    # it is ok to expect updates to be reflected after a server restart.
    @lru_cache(maxsize=2)  # noqa: B019
    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        if self.filename is None:
            return {}
        try:
            filepath = Path(self.filename)
            if not filepath.is_file():
                return {}

            from marimo._environments import script_metadata

            script_content = filepath.read_text(encoding="utf-8")
            script_config = script_metadata.loads(script_content)
            if script_config is None:
                return {}

            script_config = allowlist_script_config(
                script_config, ALLOWED_SCRIPT_CONFIG_TOP_KEYS
            )
            script_config = sanitize_pyproject_dict(
                script_config,
                (
                    ("tool", "marimo", "runtime", "auto_instantiate"),
                    ("tool", "marimo", "experimental", "isolate_apps"),
                    ("tool", "marimo", "display", "custom_css"),
                ),
            )

            marimo_config = get_marimo_config_from_pyproject_dict(
                script_config
            )
            if marimo_config is None:
                return {}

            marimo_config = PyprojectConfigReader(
                self.filename
            )._resolve_dotenv(marimo_config)

            # PEP 723 script metadata cannot anchor cache-signing trust.
            marimo_config = strip_untrusted_config(marimo_config)

        except Exception as e:
            LOGGER.warning("Failed to read script config: %s", e)
            return {}

        if hide_secrets:
            return mask_secrets_partial(marimo_config)
        return marimo_config


class UserConfigStore(ConfigStore):
    """Read explicit user settings and persist updates to the discovered file.

    `read()` contributes stored values without defaults; `get_config()`
    adds built-in defaults. In the default hierarchy this source precedes
    project, script, and environment settings. Reads mask secrets by default.

    Discovery currently checks cwd/parent `.marimo.toml` files before home and
    XDG locations, so the selected file can still be project-local. Saving
    targets that same file, preserves masked secrets, and retains the
    behavior of writing built-in defaults alongside updates. `unset()` removes
    a stored key through the existing null-as-delete mechanism.
    """

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        values = self._load_config()
        if hide_secrets:
            values = mask_secrets_partial(cast(PartialMarimoConfig, values))
        return values

    def update(self, patch: PartialMarimoConfig | MarimoConfig) -> None:
        """Persist a patch through the existing user save behavior."""
        self.save_config(patch)

    def unset(self, path: tuple[str, ...]) -> None:
        """Remove a setting using the existing null-as-delete behavior."""
        if not path or any(not key for key in path):
            raise ValueError("A setting path must contain non-empty keys")
        patch: dict[str, Any] = {}
        current = patch
        for key in path[:-1]:
            child: dict[str, Any] = {}
            current[key] = child
            current = child
        current[path[-1]] = None
        self.update(cast(PartialMarimoConfig, patch))

    def save_config(
        self, config: MarimoConfig | PartialMarimoConfig
    ) -> MarimoConfig:
        import tomlkit

        config_path = self.get_config_path()
        LOGGER.info("Saving user configuration to %s", config_path)
        # Remove the secret placeholders from the incoming config
        config = remove_secret_placeholders(config)
        # Merge the current config with the new config
        current_config = merge_default_config(self._load_config())
        merged = merge_config(current_config, config)
        # None-as-delete: any key whose merged value is None (typically because
        # the incoming config explicitly sent null) is removed from disk. Lets
        # the UI clear optional scalars (e.g. ai.max_tokens) without a separate
        # delete primitive.
        _drop_none_values(cast(dict[str, Any], merged))

        with open(config_path, "w", encoding="utf-8") as f:
            tomlkit.dump(merged, f, sort_keys=True)

        return merge_default_config(merged)

    def save_config_if_missing(self) -> None:
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                self.save_config(DEFAULT_CONFIG)
        except Exception as e:
            LOGGER.warning("Failed to save config: %s", e)

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        current_config = merge_default_config(self._load_config())
        if hide_secrets:
            return mask_secrets(current_config)
        return current_config

    def get_config_path(self) -> str:
        return get_or_create_user_config_path()

    def _load_config(self) -> PartialMarimoConfig | MarimoConfig:
        """Read explicit user settings without injecting defaults."""
        try:
            path = self.get_config_path()
        except OSError as e:
            path = None
            LOGGER.warning(
                "Encountered error when searching for config: %s", e
            )

        if path is not None:
            LOGGER.debug("Using config at %s", path)
            try:
                user_config = read_marimo_config(path)
            except Exception as e:
                LOGGER.error("Failed to read user config at %s", path)
                LOGGER.error(str(e))
                return {}
            if not is_trusted_user_config_path(path):
                # A `.marimo.toml` discovered by walking up from the cwd is
                # project-origin, not user-owned. Strip its cache-trust keys
                # like any other untrusted layer.
                user_config = strip_untrusted_config(
                    user_config, is_user_layer=True
                )
            return _drop_hollow_dotenv(user_config)
        else:
            LOGGER.debug("No config found; loading default settings.")
        return {}


class InMemoryConfigReader(ConfigReader):
    """Supply an in-memory patch without reading or writing a config file.

    Used by `MarimoConfigManager.with_overrides()` for invocation-specific
    settings, such as export execution options, sandbox package management,
    and the CLI traceback flag. The manager determines precedence by where it
    inserts the source; this object only returns values and masks secrets.
    """

    def __init__(self, override_config: PartialMarimoConfig) -> None:
        self.override_config = override_config

    def read(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig | MarimoConfig:
        return self.get_config(hide_secrets=hide_secrets)

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        if hide_secrets:
            return mask_secrets_partial(self.override_config)
        return self.override_config


def _is_home_directory(path: Path) -> bool:
    home = os.path.expanduser("~")
    if home == "~":
        return False
    return os.path.realpath(path) == os.path.realpath(home)


def _drop_hollow_dotenv(config: PartialMarimoConfig) -> PartialMarimoConfig:
    """Drop an empty `runtime.dotenv`, which is a masked value and not a choice."""
    # NB. Reading the configuration blanks runtime.dotenv by emptying the list,
    # and marimo 0.18 and earlier saved that masked copy straight back to disk,
    # so an empty list there means "hidden", not "load nothing". Keeping it
    # would let a stale file suppress the .env next to the notebook.
    runtime = config.get("runtime")
    if runtime is None or runtime.get("dotenv") != []:
        return config
    without_dotenv = {k: v for k, v in runtime.items() if k != "dotenv"}
    return {**config, "runtime": cast(RuntimeConfig, without_dotenv)}


def _drop_none_values(d: dict[str, Any]) -> None:
    """Recursively remove keys whose value is None, in place."""
    for key in list(d):
        v = d[key]
        if v is None:
            del d[key]
        elif isinstance(v, dict):
            _drop_none_values(v)

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any, cast

import msgspec

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    DEFAULT_CONFIG_ENV_VARS,
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
from marimo._config.config_schema import MarimoConfig as MarimoConfigSchema
from marimo._config.packages import PackageManagerKind
from marimo._config.provenance import (
    ConfigLayer,
    ConfigPath,
    ConfigSource,
    ResolvedConfig,
    env_var_name,
    format_config_source,
)
from marimo._config.reader import (
    ALLOWED_SCRIPT_CONFIG_TOP_KEYS,
    ConfigReader,
    allowlist_script_config,
    find_nearest_pyproject_toml,
    get_marimo_config_from_pyproject_dict,
    read_marimo_config,
    read_pyproject_marimo_config,
    sanitize_pyproject_dict,
    strip_untrusted_config,
)
from marimo._config.resolver import (
    merge_config_patches,
    merge_resolved_configs,
    resolve_config,
    resolve_config_with_sources,
)
from marimo._config.secrets import (
    redact_secrets,
    redact_secrets_partial,
    remove_secret_placeholders,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.utils import (
    deep_copy,
    get_or_create_user_config_path,
    is_trusted_user_config_path,
)
from marimo._utils.env import env_to_value

LOGGER = _loggers.marimo_logger()


def _validate_config(resolved: ResolvedConfig) -> None:
    try:
        MarimoConfigSchema.from_dict(cast(dict[str, object], resolved.config))
    except (
        msgspec.ValidationError,
        TypeError,
        ValueError,
        AttributeError,
    ) as error:
        match = re.search(r" - at `\$(.*?)`$", str(error))
        # msgspec hides dictionary keys as [...] and indexes into lists whose
        # provenance is tracked as a single value.
        path = (
            [
                field or None
                for field, index in re.findall(
                    r"\.([^.[\]]+)|\[(\.\.\.|\d+)\]", match[1]
                )
                if not index.isdigit()
            ]
            if match
            else []
        )
        sources = dict.fromkeys(
            format_config_source(origin, source)
            for origin, source in resolved.origins.items()
            if all(
                field is None or field == key
                for field, key in zip(path, origin, strict=False)
            )
        )
        LOGGER.error(
            "Invalid configuration from %s: %s",
            ", ".join(sources),
            error,
            extra={"omit_log_prefix": True},
        )


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


class MarimoConfigManager:
    def __init__(
        self,
        user_config_mgr: UserConfigStore,
        *partials: ConfigReader,
    ) -> None:
        self.user_config_mgr = user_config_mgr
        # Security partials are pulled out and always merged last (after every
        # other partial, including any added by with_overrides()), so the
        # enforcements they apply cannot be re-enabled by a lower-priority
        # config source. See SecurityConfigReader.
        self.partials = tuple(
            p for p in partials if not isinstance(p, SecurityConfigReader)
        )
        self.security_partials = tuple(
            p for p in partials if isinstance(p, SecurityConfigReader)
        )

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

    def get_user_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the user configuration"""
        config = resolve_config(
            DEFAULT_CONFIG, (self.user_config_mgr.read_layer().config,)
        )
        return redact_secrets(config) if hide_secrets else config

    def get_config_overrides(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get the configuration overrides

        Security partials are merged last, so the enforcements they apply
        cannot be overridden by any other config source.
        """
        config = self._read_overrides()
        return redact_secrets_partial(config) if hide_secrets else config

    def _read_overrides(self) -> PartialMarimoConfig:
        return merge_config_patches(
            reader.read_layer().config
            for reader in (*self.partials, *self.security_partials)
        )

    def get_config_defaults(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get contextual fallbacks, merged beneath explicit configuration."""
        config = self._read_defaults()
        return redact_secrets_partial(config) if hide_secrets else config

    def _read_defaults(self) -> PartialMarimoConfig:
        return merge_config_patches(
            _contextual_defaults(reader)
            for reader in (*self.partials, *self.security_partials)
        )

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the configuration, by merging the user configuration and the configuration overrides"""
        return self.get_config_with_sources(hide_secrets=hide_secrets).config

    def get_config_with_sources(
        self, *, hide_secrets: bool = True
    ) -> ResolvedConfig:
        """Resolve settings and their winning sources without collapsing layers."""
        readers = (*self.partials, *self.security_partials)
        layers = [
            ConfigLayer(
                _contextual_defaults(reader),
                "inferred",
            )
            for reader in readers
        ]
        layers.append(
            ConfigLayer(
                cast(PartialMarimoConfig, DEFAULT_CONFIG),
                "default",
            )
        )
        layers.append(
            ConfigLayer(
                {
                    "package_management": {
                        "manager": DEFAULT_CONFIG["package_management"][
                            "manager"
                        ]
                    }
                },
                "inferred",
            )
        )
        if DEFAULT_CONFIG_ENV_VARS:
            runtime = cast(dict[str, Any], DEFAULT_CONFIG["runtime"])
            layers.append(
                ConfigLayer(
                    {
                        "runtime": cast(
                            RuntimeConfig,
                            {
                                path[1]: runtime[path[1]]
                                for path in DEFAULT_CONFIG_ENV_VARS
                            },
                        )
                    },
                    "env_var",
                )
            )
        layers.append(self.user_config_mgr.read_layer())
        overrides = resolve_config_with_sources(
            reader.read_layer() for reader in readers
        )
        # Record-replacement merges are not associative. Preserve the existing
        # grouping of overrides before merging them with user settings.
        resolved = merge_resolved_configs(
            resolve_config_with_sources(layers), overrides
        )
        _validate_config(resolved)
        if hide_secrets:
            resolved.config = redact_secrets(resolved.config)
        return resolved

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
        return self.with_partial(OverrideConfigReader(overrides))

    def with_partial(self, partial: ConfigReader) -> MarimoConfigManager:
        """Get a new config manager with the given partial reader layered on

        The source is read unmasked during resolution; masking is applied only
        when configuration values are returned to callers.
        """
        return MarimoConfigManager(
            self.user_config_mgr,
            *self.partials,
            partial,
            *self.security_partials,
        )


class PyprojectConfigReader(ConfigReader):
    """Read `tool.marimo` settings from the nearest `pyproject.toml`."""

    def __init__(self, start_path: str) -> None:
        self.start_path = start_path
        self.pyproject_path = find_nearest_pyproject_toml(start_path)

    @property
    def source(self) -> ConfigSource:
        return (
            self.pyproject_path
            if self.pyproject_path is not None
            else "default"
        )

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

    def read(self) -> PartialMarimoConfig:
        return cast(PartialMarimoConfig, deep_copy(self._read_config()))

    # Source changes are picked up after a server restart.
    @lru_cache(maxsize=2)  # noqa: B019
    def _read_config(self) -> PartialMarimoConfig:
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
            LOGGER.error(
                'Could not load project configuration from %s: "%s"\n'
                "Settings from this file were skipped; other configuration sources still apply.",
                self.source,
                e,
                extra={"omit_log_prefix": True},
            )
            return {}

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
            # The manager supplies contextual defaults below explicit settings.
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
        custom_css = display.get("custom_css")

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
    @property
    def source(self) -> ConfigSource:
        return "env_var"

    def _maybe_override_from_env(
        self,
        path: ConfigPath,
        config: PartialMarimoConfig,
        allowed_values: tuple[Any, ...] | None = None,
    ) -> None:
        key = env_var_name(path)
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

    def read(self) -> PartialMarimoConfig:
        """Get the configuration, as a partial configuration"""
        project_config: PartialMarimoConfig = {}
        # We could do this dynamically, but list explicitly for now to reduce
        # surface area
        self._maybe_override_from_env(
            ("runtime", "auto_instantiate"),
            project_config,
        )
        self._maybe_override_from_env(
            ("server", "transport"),
            project_config,
            allowed_values=("websocket", "sse"),
        )
        self._maybe_override_from_env(
            ("runtime", "on_cell_change"),
            project_config,
            allowed_values=("lazy", "autorun"),
        )
        return project_config


class SecurityConfigReader(ConfigReader):
    """Machine-wide security enforcements that always take precedence.

    `MarimoConfigManager` merges partials of this type last, after every other
    config source (including any added by `with_overrides()`), so the
    enforcements they apply cannot be re-enabled by a user, project, script,
    env, or runtime override. Intended for restrictions set by infra admins
    outside the user's control, e.g. in a devpod or container spec.

    This is the surface area for future required enforcements; today it only
    handles `MARIMO_RESTRICT_SHARING`.
    """

    @property
    def source(self) -> ConfigSource:
        return "env_var"

    def read(self) -> PartialMarimoConfig:
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

    @property
    def source(self) -> ConfigSource:
        return Path(self.filename) if self.filename is not None else "default"

    def read(self) -> PartialMarimoConfig:
        return cast(PartialMarimoConfig, deep_copy(self._read_config()))

    # Source changes are picked up after a server restart.
    @lru_cache(maxsize=2)  # noqa: B019
    def _read_config(self) -> PartialMarimoConfig:
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
                script_config, location=self.filename
            )
            if marimo_config is None:
                return {}

            marimo_config = PyprojectConfigReader(
                self.filename
            )._resolve_dotenv(marimo_config)

            # PEP 723 script metadata cannot anchor cache-signing trust.
            marimo_config = strip_untrusted_config(marimo_config)

        except Exception as e:
            LOGGER.error(
                'Could not load script configuration from %s: "%s"\n'
                "Settings from this file were skipped; other configuration sources still apply.",
                self.source,
                e,
                extra={"omit_log_prefix": True},
            )
            return {}

        return marimo_config


class UserConfigStore(ConfigReader):
    """Read and write the user configuration"""

    @property
    def source(self) -> ConfigSource:
        try:
            return Path(self.get_config_path())
        except OSError:
            return "default"

    def save_config(
        self, config: MarimoConfig | PartialMarimoConfig
    ) -> MarimoConfig:
        import tomlkit

        config_path = self.get_config_path()
        LOGGER.info("Saving user configuration to %s", config_path)
        # Remove the secret placeholders from the incoming config
        config = remove_secret_placeholders(config)
        # Merge the current config with the new config
        current_config = resolve_config(DEFAULT_CONFIG, (self.read(),))
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

    def read(self) -> PartialMarimoConfig:
        """Read explicit user settings without applying defaults or masking."""
        return cast(PartialMarimoConfig, deep_copy(self._load_config()))

    def get_config_path(self) -> str:
        return get_or_create_user_config_path()

    def _load_config(self) -> PartialMarimoConfig:
        """
        Load configuration, taking into account user config file, if any.
        """
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
                LOGGER.error(
                    'Could not load configuration from %s: "%s"\n'
                    "Settings from this file were skipped; other configuration sources still apply.",
                    path,
                    e,
                    extra={"omit_log_prefix": True},
                )
                return {}
            if not is_trusted_user_config_path(path):
                # A `.marimo.toml` discovered by walking up from the cwd is
                # project-origin, not user-owned. Strip its cache-trust keys
                # like any other untrusted layer.
                user_config = strip_untrusted_config(
                    user_config, is_user_layer=True
                )
            return user_config
        else:
            LOGGER.debug("No config found; loading default settings.")
        return {}


class OverrideConfigReader(ConfigReader):
    """Read the configuration, with overrides"""

    def __init__(self, override_config: PartialMarimoConfig) -> None:
        self.override_config = deep_copy(override_config)

    def read(self) -> PartialMarimoConfig:
        return cast(PartialMarimoConfig, deep_copy(self.override_config))


def _contextual_defaults(reader: ConfigReader) -> PartialMarimoConfig:
    """Infer fallback dotenv paths; the runtime loads the selected files later."""
    if isinstance(reader, ScriptConfigReader):
        if reader.filename is None:
            return {}
        project = PyprojectConfigReader(reader.filename)
    elif isinstance(reader, PyprojectConfigReader):
        project = reader
    else:
        return {}

    root = project._dotenv_root
    if project.pyproject_path is None and _is_home_directory(root):
        # Avoid exposing ~/.env merely because a workspace opened at home.
        return {}
    return cast(
        PartialMarimoConfig,
        {"runtime": {"dotenv": [str((root / ".env").absolute())]}},
    )


def _is_home_directory(path: Path) -> bool:
    home = os.path.expanduser("~")
    if home == "~":
        return False
    return os.path.realpath(path) == os.path.realpath(home)


def _drop_none_values(d: dict[str, Any]) -> None:
    """Recursively remove keys whose value is None, in place."""
    for key in list(d):
        v = d[key]
        if v is None:
            del d[key]
        elif isinstance(v, dict):
            _drop_none_values(v)

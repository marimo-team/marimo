# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from abc import abstractmethod
from pathlib import Path
from typing import Optional, Union, cast

from marimo import _loggers
from marimo._config.config import (
    DEFAULT_CONFIG,
    MarimoConfig,
    PartialMarimoConfig,
    Theme,
    WidthType,
    merge_config,
    merge_default_config,
)
from marimo._config.packages import PackageManagerKind
from marimo._config.reader import (
    get_marimo_config_from_pyproject_dict,
    read_marimo_config,
    read_pyproject_marimo_config,
)
from marimo._config.secrets import (
    mask_secrets,
    mask_secrets_partial,
    remove_secret_placeholders,
)
from marimo._config.utils import (
    get_or_create_user_config_path,
)

LOGGER = _loggers.marimo_logger()


def get_default_config_manager(
    *, current_path: Optional[str]
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
        UserConfigManager(),
        ProjectConfigManager(current_path),
        ScriptConfigManager(current_path),
    )


class MarimoConfigReader:
    @abstractmethod
    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the configuration, optionally hiding secrets"""
        pass

    # Convenience methods for common access patterns

    @property
    def default_width(self) -> WidthType:
        return self.get_config()["display"]["default_width"]

    @property
    def theme(self) -> Theme:
        return self.get_config()["display"]["theme"]

    @property
    def package_manager(self) -> PackageManagerKind:
        return self.get_config()["package_management"]["manager"]


class MarimoConfigManager(MarimoConfigReader):
    def __init__(
        self,
        user_config_mgr: UserConfigManager,
        *partials: PartialMarimoConfigReader,
    ) -> None:
        self.user_config_mgr = user_config_mgr
        self.partials = partials

    def get_user_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the user configuration"""
        return self.user_config_mgr.get_config(hide_secrets=hide_secrets)

    def get_config_overrides(
        self, *, hide_secrets: bool = True
    ) -> PartialMarimoConfig:
        """Get the configuration overrides"""
        if not self.partials:
            return {}
        if len(self.partials) == 1:
            return self.partials[0].get_config(hide_secrets=hide_secrets)
        result: MarimoConfig = cast(MarimoConfig, {})
        for partial in self.partials:
            result = merge_config(
                result, partial.get_config(hide_secrets=hide_secrets)
            )
        return cast(PartialMarimoConfig, result)

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        """Get the configuration, by merging the user configuration and the configuration overrides"""
        return merge_config(
            self.get_user_config(hide_secrets=hide_secrets),
            self.get_config_overrides(hide_secrets=hide_secrets),
        )

    def save_config(
        self, config: Union[MarimoConfig, PartialMarimoConfig]
    ) -> MarimoConfig:
        """Save the configuration"""
        return self.user_config_mgr.save_config(config)

    def with_overrides(
        self, overrides: PartialMarimoConfig
    ) -> MarimoConfigManager:
        """Get a new config manager with the given overrides"""
        return MarimoConfigManager(
            self.user_config_mgr,
            *self.partials,
            MarimoConfigReaderWithOverrides(overrides),
        )


@abstractmethod
class PartialMarimoConfigReader:
    @abstractmethod
    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        """Get the configuration, as a partial configuration"""
        pass


class ProjectConfigManager(PartialMarimoConfigReader):
    """Read the project configuration"""

    def __init__(self, start_path: str) -> None:
        self.start_path = start_path

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        try:
            project_config = read_pyproject_marimo_config(self.start_path)
            if project_config is None:
                return {}
            project_config = self._resolve_pythonpath(project_config)
            project_config = self._resolve_dotenv(project_config)
        except Exception as e:
            LOGGER.warning("Failed to read project config: %s", e)
            return {}

        if hide_secrets:
            return mask_secrets_partial(project_config)
        return project_config

    def _resolve_pythonpath(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        if "runtime" not in config:
            return config

        if "pythonpath" not in config["runtime"]:
            return config

        pythonpath = config["runtime"]["pythonpath"]

        if not isinstance(pythonpath, list):
            return config

        pythonpath = [
            os.path.abspath(os.path.join(self.start_path, path))
            for path in pythonpath
        ]
        return {
            **config,
            "runtime": {**config["runtime"], "pythonpath": pythonpath},
        }

    def _resolve_dotenv(
        self, config: PartialMarimoConfig
    ) -> PartialMarimoConfig:
        if "runtime" not in config:
            return config

        if "dotenv" not in config["runtime"]:
            return config

        dotenv = config["runtime"]["dotenv"]

        if not isinstance(dotenv, list):
            return config

        dotenv = [
            os.path.abspath(os.path.join(self.start_path, path))
            for path in dotenv
        ]
        return {**config, "runtime": {**config["runtime"], "dotenv": dotenv}}


class ScriptConfigManager(PartialMarimoConfigReader):
    """Read the script configuration following PEP 723

    This looks like a pyproject.toml serialized as a comment in the header
    of the script.
    """

    def __init__(self, filename: Optional[str]) -> None:
        self.filename = filename

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        if self.filename is None:
            return {}
        try:
            filepath = Path(self.filename)
            if not filepath.is_file():
                return {}

            from marimo._utils.scripts import read_pyproject_from_script

            script_content = filepath.read_text(encoding="utf-8")
            script_config = read_pyproject_from_script(script_content)
            if script_config is None:
                return {}

            marimo_config = get_marimo_config_from_pyproject_dict(
                script_config
            )
            if marimo_config is None:
                return {}

        except Exception as e:
            LOGGER.warning("Failed to read script config: %s", e)
            return {}

        if hide_secrets:
            return mask_secrets_partial(marimo_config)
        return marimo_config


class UserConfigManager(MarimoConfigReader):
    """Read and write the user configuration"""

    def save_config(
        self, config: Union[MarimoConfig, PartialMarimoConfig]
    ) -> MarimoConfig:
        import tomlkit

        config_path = self.get_config_path()
        LOGGER.debug("Saving user configuration to %s", config_path)
        # Remove the secret placeholders from the incoming config
        config = remove_secret_placeholders(config)
        # Merge the current config with the new config
        current_config = self._load_config()
        merged = merge_config(current_config, config)

        with open(config_path, "w", encoding="utf-8") as f:
            tomlkit.dump(merged, f)

        return merge_default_config(merged)

    def save_config_if_missing(self) -> None:
        try:
            config_path = self.get_config_path()
            if not os.path.exists(config_path):
                self.save_config(DEFAULT_CONFIG)
        except Exception as e:
            LOGGER.warning("Failed to save config: %s", e)

    def get_config(self, *, hide_secrets: bool = True) -> MarimoConfig:
        current_config = self._load_config()
        if hide_secrets:
            return mask_secrets(current_config)
        return current_config

    def get_config_path(self) -> str:
        return get_or_create_user_config_path()

    def _load_config(self) -> MarimoConfig:
        """
        Load configuration, taking into account user config file, if any.
        """
        try:
            path = self.get_config_path()
        except OSError as e:
            path = None
            LOGGER.warning(
                "Encountered error when searching for config: %s", str(e)
            )

        if path is not None:
            LOGGER.debug("Using config at %s", path)
            try:
                user_config = read_marimo_config(path)
            except Exception as e:
                LOGGER.error("Failed to read user config at %s", path)
                LOGGER.error(str(e))
                return DEFAULT_CONFIG
            return merge_default_config(user_config)
        else:
            LOGGER.debug("No config found; loading default settings.")
        return DEFAULT_CONFIG


class MarimoConfigReaderWithOverrides(PartialMarimoConfigReader):
    """Read the configuration, with overrides"""

    def __init__(self, override_config: PartialMarimoConfig) -> None:
        self.override_config = override_config

    def get_config(self, *, hide_secrets: bool = True) -> PartialMarimoConfig:
        if hide_secrets:
            return mask_secrets_partial(self.override_config)
        return self.override_config

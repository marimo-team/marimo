# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import Callable, Optional

from marimo import _loggers
from marimo._config.config import Theme

LOGGER = _loggers.marimo_logger()


# Abstract base class for formatters that are installed at runtime.
class FormatterFactory(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def package_name() -> Optional[str]:
        """Name of third-party package that this formatter is for

        **Important**: should not actually import the package, since that will
        slow down all imports.

        Return `None` if the formatter isn't for any specific package.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def register(self) -> Callable[[], None] | None:
        """Registers formatters.

        Formatters can be registered using the formatters.formatter decorator.

        Optionally returns a handle to undo side-effects, such as module
        patches.
        """
        raise NotImplementedError

    def apply_theme(self, theme: Theme) -> None:
        """
        Apply the theme (light/dark) to third party libraries.
        If the theme is set to "system", then we fallback to "light".

        Args:
            theme: The theme to apply.
        """
        del theme
        return

    def apply_theme_safe(self, theme: Theme) -> None:
        """
        Apply the theme (light/dark) to third party libraries.
        If the theme is set to "system", then we fallback to "light".

        Args:
            theme: The theme to apply.
        """
        try:
            self.apply_theme(theme)
        except Exception as e:
            LOGGER.error(
                f"Error applying theme {theme} fro {self.package_name()}: {e}"
            )

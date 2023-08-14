# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import abc
from typing import Optional


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
    def register(self) -> None:
        """Registers formatters.

        Formatters can be registered using the formatters.formatter decorator.
        """
        raise NotImplementedError

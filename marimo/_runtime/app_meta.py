# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional

from marimo._config.utils import load_config
from marimo._runtime.context.utils import get_mode


class AppMeta:
    """
    Metadata about the app.

    This is used to store metadata about the app
    that is not part of the app's code or state.
    """

    def __init__(self) -> None:
        self.user_config = load_config()

    @property
    def theme(self) -> str:
        """The display theme of the app."""
        theme = self.user_config["display"]["theme"] or "light"
        if theme == "system":
            # TODO(mscolnick): have frontend tell the backend the system theme
            return "light"
        return theme

    @property
    def mode(self) -> Optional[Literal["edit", "run", "script"]]:
        """The mode of the app (edit/run/script) or None."""
        return get_mode()

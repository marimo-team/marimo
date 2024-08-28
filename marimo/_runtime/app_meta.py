# Copyright 2024 Marimo. All rights reserved.
from marimo._config.utils import load_config


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

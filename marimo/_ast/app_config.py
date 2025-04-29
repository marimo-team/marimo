# Copyright 2025 Marimo. All rights reserved.
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from marimo import _loggers
from marimo._config.config import SqlOutputType, WidthType

LOGGER = _loggers.marimo_logger()


@dataclass
class _AppConfig:
    """Program-specific configuration.

    Configuration for frontends or runtimes that is specific to
    a single marimo program.
    """

    width: WidthType = "compact"

    app_title: Optional[str] = None

    # The file path of the layout file, relative to the app file.
    layout_file: Optional[str] = None

    # CSS file, relative to the app file
    css_file: Optional[str] = None

    # HTML head file, relative to the app file
    html_head_file: Optional[str] = None

    # Whether to automatically download the app as HTML and Markdown
    auto_download: list[Literal["html", "markdown"]] = field(
        default_factory=list
    )

    # The type of SQL output to display
    sql_output: SqlOutputType = "auto"

    @staticmethod
    def from_untrusted_dict(
        updates: dict[str, Any], silent: bool = False
    ) -> "_AppConfig":
        # Certain flags are useful to pass to App for construction, but
        # shouldn't make it into the config. (e.g. the _filename flag is
        # internal)
        other_allowed = {"_filename"}
        config = _AppConfig()
        for key in updates:
            if hasattr(config, key):
                config.__setattr__(key, updates[key])
            elif key not in other_allowed:
                if not silent:
                    LOGGER.warning(
                        f"Unrecognized key '{key}' in app config. Ignoring."
                    )
        return config

    def asdict(self) -> dict[str, Any]:
        # Used for experimental hooks which start with _
        return {
            k: v for (k, v) in asdict(self).items() if not k.startswith("_")
        }

    def update(self, updates: dict[str, Any]) -> "_AppConfig":
        config_dict = asdict(self)
        for key in updates:
            if key in config_dict:
                self.__setattr__(key, updates[key])

        return self

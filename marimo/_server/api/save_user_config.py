# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import tomlkit
import tornado.web

from marimo import _loggers
from marimo._config.config import MarimoConfig, configure
from marimo._config.utils import get_config_path
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw
from marimo._server.api.status import HTTPStatus

LOGGER = _loggers.marimo_logger()


_INDENT = " " * 4


def _format_configuration(config: Any, depth: int) -> str:
    if isinstance(config, dict):
        key_indent = _INDENT * depth
        closing_brace_indent = _INDENT * (depth - 1)
        lines = ["{"]
        for key in sorted(config.keys()):
            value = _format_configuration(config[key], depth=depth + 1)
            lines.append(key_indent + f'"{key}": {value}')
        lines.append(closing_brace_indent + "},")
        return "\n".join(lines)
    elif isinstance(config, str):
        return f'"{config}",'
    else:
        return str(config) + ","


@dataclass
class SaveUserConfiguration:
    # user configuration
    config: MarimoConfig


class SaveUserConfigurationHandler(tornado.web.RequestHandler):
    """Save user configuration to disk."""

    @sessions.requires_edit
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, SaveUserConfiguration)
        config_path = get_config_path()
        config_dir = (
            os.path.dirname(config_path)
            if config_path
            else os.path.expanduser("~")
        )
        LOGGER.debug("Saving user configuration to %s", config_dir)
        config_path = os.path.join(config_dir, ".marimo.toml")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                tomlkit.dump(args.config, f)
        except Exception as e:
            raise tornado.web.HTTPError(
                HTTPStatus.SERVER_ERROR,
                reason="Failed to save file: {0}".format(str(e)),
            ) from e

        # Update the server's view of the config
        config = configure(args.config)
        LOGGER.debug("Starting copilot server")
        if config["completion"]["copilot"]:
            sessions.get_manager().start_lsp_server()
        # Update the kernel's view of the config
        session.queue.put(requests.ConfigurationRequest(str(args.config)))

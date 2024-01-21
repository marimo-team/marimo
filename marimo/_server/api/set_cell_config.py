# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import server_utils as sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw


@dataclass
class SetCellConfig:
    # Map from Cell ID to (possibly partial) CellConfig
    configs: Dict[CellId_t, Dict[str, object]]


class SetCellConfigHandler(ValidatedHandler):
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, SetCellConfig)
        session.control_queue.put(requests.SetCellConfigRequest(args.configs))

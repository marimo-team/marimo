# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import tornado.web

from marimo._ast.cell import CellId_t
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class SetCellConfig:
    # Map from Cell ID to (possibily partial) CellConfig
    configs: Dict[CellId_t, Dict[str, object]]


class SetCellConfigHandler(tornado.web.RequestHandler):
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, SetCellConfig)
        session.queue.put(requests.SetCellConfigRequest(args.configs))

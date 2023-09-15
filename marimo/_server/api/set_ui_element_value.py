# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import tornado.web

from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class SetUIElementValue:
    # ids of UI elements whose values we'll set
    object_ids: List[str]
    # value of each UI element; same length as object_ids
    values: List[Any]


class SetUIElementValueHandler(tornado.web.RequestHandler):
    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, SetUIElementValue)
        session.queue.put(
            requests.SetUIElementValueRequest(
                zip(
                    args.object_ids,
                    args.values,
                )
            )
        )

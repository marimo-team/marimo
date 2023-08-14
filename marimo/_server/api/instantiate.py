# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tornado.web

from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class Instantiate:
    # unique identifiers for UIElements
    object_ids: list[str]
    # initial value of each UIElement
    values: list[Any]


class InstantiateHandler(tornado.web.RequestHandler):
    """Instantiate an app

    Run all cells, parametrized by values for UI elements, if any.
    """

    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, Instantiate)
        mgr = sessions.get_manager()
        app_data = mgr.app_data()
        request = requests.CreationRequest(
            execution_requests=tuple(
                requests.ExecutionRequest(cid, cell_data.code)
                for cid, cell_data in app_data.items()
            ),
            set_ui_element_value_request=requests.SetUIElementValueRequest(
                zip(args.object_ids, args.values)
            ),
        )
        session.queue.put(request)

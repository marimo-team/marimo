# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

import tornado.web

from marimo._ast.app import App
from marimo._runtime import requests
from marimo._server import sessions
from marimo._server.api.model import parse_raw


@dataclass
class Instantiate:
    # unique identifiers for UIElements
    object_ids: List[str]
    # initial value of each UIElement
    values: List[Any]


class InstantiateHandler(tornado.web.RequestHandler):
    """Instantiate an app

    Run all cells, parametrized by values for UI elements, if any.
    """

    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, Instantiate)
        mgr = sessions.get_manager()
        app = mgr.load_app()
        execution_requests: tuple[requests.ExecutionRequest, ...]
        if app is None:
            # Instantiating an empty app
            # TODO(akshayka): In this case, don't need to run anything ...
            execution_requests = (
                requests.ExecutionRequest(App()._create_cell_id(None), ""),
            )
        else:
            execution_requests = tuple(
                requests.ExecutionRequest(cell_data.cell_id, cell_data.code)
                for cell_data in app._cell_data.values()
            )

        request = requests.CreationRequest(
            execution_requests=execution_requests,
            set_ui_element_value_request=requests.SetUIElementValueRequest(
                zip(args.object_ids, args.values)
            ),
        )
        session.queue.put(request)

# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import tornado.web

from marimo import _loggers
from marimo._runtime import requests
from marimo._server import sessions
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()


@dataclass
class FunctionCall:
    # unique token associated with the function call
    function_call_id: str
    namespace: str
    function_name: str
    args: Dict[str, Any]


class FunctionHandler(tornado.web.RequestHandler):
    """Invoke an RPC"""

    def post(self) -> None:
        session = sessions.require_session_from_header(self.request.headers)
        args = parse_raw(self.request.body, FunctionCall)
        request = requests.FunctionCallRequest(
            function_call_id=args.function_call_id,
            namespace=args.namespace,
            function_name=args.function_name,
            args=args.args,
        )
        session.queue.put(request)

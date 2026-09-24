# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from websockets.sync.server import Server, ServerConnection, serve

if TYPE_CHECKING:
    from websockets.http11 import Request, Response


def pylsp_connection(websocket: ServerConnection) -> None:
    # pylsp's own WebSocket launcher cannot restrict its host or handshake.
    from pylsp.python_lsp import PythonLSPServer  # type: ignore[import-not-found,import-untyped]

    def consume(message: Any) -> None:
        websocket.send(json.dumps(message, ensure_ascii=False))

    handler = PythonLSPServer(
        rx=None, tx=None, consumer=consume, check_parent_process=True
    )

    try:
        for message in websocket:
            handler.consume(json.loads(message))
    finally:
        # Release worker threads and file watchers when a client disconnects.
        try:
            if handler.config is not None and not handler._shutdown:
                handler.m_shutdown()
        finally:
            handler.m_exit()


def create_server(port: int, token: str) -> Server:
    if not token:
        raise ValueError("MARIMO_LSP_TOKEN must be set")

    def authenticate(
        connection: ServerConnection, request: Request
    ) -> Response | None:
        tokens = request.headers.get_all("Marimo-LSP-Token")
        if (
            len(tokens) != 1
            or not tokens[0].isascii()
            or not secrets.compare_digest(tokens[0].encode(), token.encode())
        ):
            return connection.respond(HTTPStatus.FORBIDDEN, "Forbidden\n")
        return None

    return serve(
        pylsp_connection,
        host="127.0.0.1",
        port=port,
        origins=[None],
        process_request=authenticate,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--log-file", required=True)
    args = parser.parse_args()
    # WebSocket debug logging includes the private handshake credential.
    logging.basicConfig(filename=args.log_file, level=logging.INFO)
    with create_server(
        args.port, os.environ.get("MARIMO_LSP_TOKEN", "")
    ) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()

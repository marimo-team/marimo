# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ssl
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.exceptions import HTTPException

from marimo._server.ai.config import AnyProviderConfig
from marimo._utils.http import HTTPStatus

if TYPE_CHECKING:
    from openai import AsyncOpenAI


def create_openai_client(
    config: AnyProviderConfig, *, follow_redirects: bool | None = None
) -> AsyncOpenAI:
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient

    for path, label in (
        (config.ca_bundle_path, "CA Bundle"),
        (config.client_pem, "Client PEM"),
    ):
        if path and not Path(path).exists():
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"{label} is not a valid path or does not exist",
            )

    verify: bool | ssl.SSLContext = (
        config.ssl_verify if config.ssl_verify is not None else True
    )
    if verify and (config.ca_bundle_path or config.client_pem):
        if config.ca_bundle_path:
            verify = ssl.create_default_context(cafile=config.ca_bundle_path)
        else:
            verify = ssl.create_default_context()
        if config.client_pem:
            verify.load_cert_chain(certfile=config.client_pem)

    client = None
    if follow_redirects is not None:
        client = DefaultAsyncHttpxClient(
            verify=verify, follow_redirects=follow_redirects
        )
    elif verify is not True:
        client = DefaultAsyncHttpxClient(verify=verify)

    headers = {"api-key": config.api_key, **(config.extra_headers or {})}
    if client is not None:
        return AsyncOpenAI(
            default_headers=headers,
            api_key=config.api_key,
            base_url=config.base_url or None,
            project=config.project or None,
            http_client=client,
        )
    return AsyncOpenAI(
        default_headers=headers,
        api_key=config.api_key,
        base_url=config.base_url or None,
        project=config.project or None,
    )

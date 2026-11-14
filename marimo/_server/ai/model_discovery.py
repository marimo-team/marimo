# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import replace
from http import HTTPStatus
from urllib.parse import urlsplit

from starlette.exceptions import HTTPException

from marimo._dependencies.dependencies import DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.openai_client import create_openai_client
from marimo._server.models.models import ProviderModel


async def discover_models(config: AnyProviderConfig) -> list[ProviderModel]:
    if not config.base_url:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="A saved provider base URL is required.",
        )
    DependencyManager.openai.require("for model discovery")
    from httpx2 import URL, InvalidURL
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        Omit,
    )

    try:
        target = urlsplit(config.base_url)
        url = URL(config.base_url)
        valid_url = (
            url.scheme in ("http", "https")
            and url.host
            and (target.port is None or 0 <= target.port <= 65535)
            and target.username is None
            and target.password is None
            and not target.query
            and not target.fragment
        )
    except (InvalidURL, ValueError):
        valid_url = False
    if not valid_url:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid provider base URL.",
        )

    # The SDK requires a key even for unauthenticated local catalogs.
    client_config = replace(config, api_key=config.api_key or "unused")
    headers: dict[str, Omit] = {}
    if not config.api_key:
        configured_headers = {
            key.lower() for key in (config.extra_headers or {})
        }
        for header_name in ("Authorization", "api-key"):
            if header_name.lower() not in configured_headers:
                headers[header_name] = Omit()
    try:
        async with create_openai_client(
            client_config, follow_redirects=False
        ) as client:
            payload = await client.get(
                "models",
                cast_to=object,
                options={
                    "timeout": 20.0,
                    "max_retries": 0,
                    "headers": headers,
                },
            )
    except APITimeoutError:
        raise HTTPException(
            status_code=HTTPStatus.GATEWAY_TIMEOUT,
            detail="Provider model discovery timed out.",
        ) from None
    except APIStatusError as exc:
        rejected = exc.status_code in (401, 403)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST
            if rejected
            else HTTPStatus.BAD_GATEWAY,
            detail=(
                "Provider rejected the configured credentials or access."
                if rejected
                else "Provider model catalog request failed."
            ),
        ) from None
    except (APIConnectionError, ValueError, OSError):
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Unable to load the provider model catalog.",
        ) from None

    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail="Provider returned an invalid model catalog.",
        )
    models: dict[str, ProviderModel] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        name = entry.get("name")
        models[model_id] = ProviderModel(
            id=model_id,
            name=name if isinstance(name, str) and name else model_id,
        )
    return sorted(models.values(), key=lambda model: model.id)

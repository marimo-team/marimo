# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import httpx2 as httpx
import pytest

from marimo._config.config_schema import MarimoConfig
from tests._server.api.endpoints.ws_helpers import receive_until
from tests._server.conftest import (
    get_session_config_manager,
    get_user_config_manager,
)
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from starlette.testclient import TestClient

SESSION_ID = "model-discovery-session"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}

pytestmark = pytest.mark.requires("openai")


@pytest.fixture
def configured_client(client: TestClient) -> Iterator[TestClient]:
    config = MarimoConfig.from_dict(
        {
            "ai": {
                "openrouter": {"api_key": "openrouter-key"},
                "custom_providers": {
                    "gateway": {
                        "api_key": "gateway-key",
                        "base_url": "https://gateway.example.com/v1",
                        "extra_headers": {
                            "Authorization": "Basic gateway-credentials"
                        },
                    },
                    "local": {"base_url": "http://localhost:8000/v1"},
                    "header-only": {
                        "base_url": "https://gateway.example.com/v1",
                        "extra_headers": {
                            "Authorization": "Basic gateway-credentials"
                        },
                    },
                },
            }
        }
    )
    with client.websocket_connect(
        f"/ws?session_id={SESSION_ID}", headers=HEADERS
    ) as websocket:
        receive_until("kernel-ready", websocket)
        with patch.object(
            get_session_config_manager(client),
            "get_config",
            return_value=config,
        ):
            yield client
    client.post("/api/kernel/shutdown", headers=HEADERS)


@pytest.fixture
def mock_catalog() -> Iterator[
    Callable[[Callable[[httpx.Request], httpx.Response]], None]
]:
    from openai import DefaultAsyncHttpxClient

    with patch("openai.DefaultAsyncHttpxClient") as factory:

        def install(
            handler: Callable[[httpx.Request], httpx.Response],
        ) -> None:
            factory.side_effect = lambda **kwargs: DefaultAsyncHttpxClient(
                transport=httpx.MockTransport(handler), **kwargs
            )

        yield install


@pytest.mark.parametrize(
    ("provider", "url", "authorization", "api_key"),
    [
        (
            "openrouter",
            "https://openrouter.ai/api/v1/models",
            "Bearer openrouter-key",
            "openrouter-key",
        ),
        (
            "gateway",
            "https://gateway.example.com/v1/models",
            "Basic gateway-credentials",
            "gateway-key",
        ),
        ("local", "http://localhost:8000/v1/models", None, None),
        (
            "header-only",
            "https://gateway.example.com/v1/models",
            "Basic gateway-credentials",
            None,
        ),
    ],
)
def test_discover_models(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
    provider: str,
    url: str,
    authorization: str | None,
    api_key: str | None,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "z-model"},
                    {"id": "a-model", "name": "Alpha"},
                    {"id": "a-model", "name": "Alpha updated"},
                    {"id": ""},
                    {"id": 123},
                    "invalid-entry",
                ]
            },
        )

    mock_catalog(handle)
    response = configured_client.get(
        f"/api/ai/models/{provider}", headers=HEADERS
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "models": [
            {"id": "a-model", "name": "Alpha updated"},
            {"id": "z-model", "name": "z-model"},
        ]
    }
    assert response.headers["Cache-Control"] == "no-store"
    assert len(requests) == 1
    request = requests[0]
    assert (
        str(request.url),
        request.headers.get("Authorization"),
        request.headers.get("api-key"),
    ) == (
        url,
        authorization,
        api_key,
    )


@pytest.mark.parametrize(
    ("upstream_status", "status", "detail"),
    [
        (401, 400, "Provider rejected the configured credentials or access."),
        (403, 400, "Provider rejected the configured credentials or access."),
        (302, 502, "Provider model catalog request failed."),
        (500, 502, "Provider model catalog request failed."),
    ],
)
def test_discovery_upstream_errors(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
    upstream_status: int,
    status: int,
    detail: str,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            upstream_status,
            headers={"Location": "https://other.example.com/models"},
            json={"error": "upstream-secret"},
        )

    mock_catalog(handle)
    response = configured_client.get("/api/ai/models/gateway", headers=HEADERS)

    assert (response.status_code, response.json()) == (
        status,
        {"detail": detail},
    )
    assert len(requests) == 1


@pytest.mark.parametrize("payload", [{}, {"data": None}, {"data": {}}])
def test_discovery_rejects_malformed_catalog(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
    payload: object,
) -> None:
    mock_catalog(lambda _: httpx.Response(200, json=payload))
    response = configured_client.get("/api/ai/models/gateway", headers=HEADERS)
    assert (response.status_code, response.json()) == (
        502,
        {"detail": "Provider returned an invalid model catalog."},
    )


def test_discovery_timeout(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream-secret", request=request)

    mock_catalog(handle)
    response = configured_client.get("/api/ai/models/gateway", headers=HEADERS)
    assert (response.status_code, response.json()) == (
        504,
        {"detail": "Provider model discovery timed out."},
    )


def test_discovery_unsupported_provider(configured_client: TestClient) -> None:
    response = configured_client.get(
        "/api/ai/models/anthropic", headers=HEADERS
    )
    assert (response.status_code, response.json()) == (
        404,
        {"detail": "Model discovery is not available."},
    )


def test_discovery_uses_environment_credentials(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "environment-key")
    config = MarimoConfig.from_dict({"ai": {}})
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": []})

    mock_catalog(handle)
    with patch.object(
        get_session_config_manager(configured_client),
        "get_config",
        return_value=config,
    ):
        response = configured_client.get(
            "/api/ai/models/openrouter", headers=HEADERS
        )

    assert (response.status_code, response.json()) == (200, {"models": []})
    assert requests[0].headers["Authorization"] == "Bearer environment-key"


def test_discovery_rejects_invalid_json(
    configured_client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
) -> None:
    mock_catalog(
        lambda _: httpx.Response(
            200,
            content="upstream-secret",
            headers={"Content-Type": "application/json"},
        )
    )
    response = configured_client.get("/api/ai/models/gateway", headers=HEADERS)
    assert (response.status_code, response.json()) == (
        502,
        {"detail": "Unable to load the provider model catalog."},
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com:bad/v1",
        "https://example.com:65536/v1",
        "https://[broken/v1",
        "https://☃.net/v1",
        "https://example.com/\x00",
        "https://example.com/v1\n",
    ],
)
def test_discovery_rejects_invalid_base_url(
    configured_client: TestClient, base_url: str
) -> None:
    config = MarimoConfig.from_dict(
        {"ai": {"custom_providers": {"gateway": {"base_url": base_url}}}}
    )
    with (
        patch.object(
            get_session_config_manager(configured_client),
            "get_config",
            return_value=config,
        ),
        patch(
            "marimo._server.ai.model_discovery.create_openai_client"
        ) as create_client,
    ):
        response = configured_client.get(
            "/api/ai/models/gateway", headers=HEADERS
        )

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "Invalid provider base URL."},
    )
    create_client.assert_not_called()


@pytest.mark.parametrize("session_id", [None, "home-session"])
def test_discovery_without_notebook_session(
    client: TestClient,
    mock_catalog: Callable[[Callable[[httpx.Request], httpx.Response]], None],
    session_id: str | None,
) -> None:
    config = MarimoConfig.from_dict(
        {"ai": {"openrouter": {"api_key": "openrouter-key"}}}
    )
    headers = token_header("fake-token")
    if session_id is not None:
        headers["Marimo-Session-Id"] = session_id
    mock_catalog(
        lambda _: httpx.Response(200, json={"data": [{"id": "model-a"}]})
    )
    with patch.object(
        get_user_config_manager(client), "get_config", return_value=config
    ):
        response = client.get("/api/ai/models/openrouter", headers=headers)
    assert (response.status_code, response.json()) == (
        200,
        {"models": [{"id": "model-a", "name": "model-a"}]},
    )

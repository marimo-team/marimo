# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from marimo import __version__
from tests._server.mocks import token_header, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}
    response = client.get("/healthz")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "healthy"}


def test_status(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/status")
    assert response.status_code == 401, response.text

    response = client.get("/api/status", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["status"] == "healthy"
    assert len(content["filenames"]) == 0
    assert content["mode"] == "edit"
    assert content["sessions"] == 0
    assert content["version"] == __version__
    assert content["lsp_running"] is False
    assert content["python_version"] is not None


def test_version(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/version")
    assert response.status_code == 401, response.text

    response = client.get("/api/version", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.text == __version__


def test_memory(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/status")
    assert response.status_code == 401, response.text

    response = client.get("/api/usage", headers=token_header())
    assert response.status_code == 200, response.text
    memory = response.json()["memory"]
    assert memory["total"] > 0
    assert memory["available"] > 0
    assert memory["used"] > 0
    assert memory["free"] > 0
    assert "has_cgroup_mem_limit" in memory
    assert isinstance(memory["has_cgroup_mem_limit"], bool)
    cpu = response.json()["cpu"]
    assert cpu["percent"] >= 0
    computer = response.json()["server"]
    assert computer["memory"] > 0
    # None, no active session
    computer = response.json()["kernel"]
    assert computer["memory"] is None


def test_connections(client: TestClient) -> None:
    # Unauthorized
    response = client.get("/api/status/connections")
    assert response.status_code == 401, response.text

    response = client.get("/api/status/connections", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.json()["active"] == 0


def test_usage_no_gpu(client: TestClient) -> None:
    with patch(
        "marimo._server.api.endpoints.health._is_gpu_available",
        return_value=False,
    ):
        response = client.get("/api/usage", headers=token_header())
    assert response.status_code == 200
    assert response.json()["gpu"] == []


def test_usage_rocm_gpu(client: TestClient) -> None:
    import pytest

    rocm_output = (
        "WARNING: AMD GPU device(s) is/are in a low-power state. "
        "Check power control/runtime_status\n"
        "\n"
        '{"card0": {"GPU use (%)": "0", '
        '"VRAM Total Memory (B)": "8573157376", '
        '"VRAM Total Used Memory (B)": "1069268992", '
        '"Card Series": "AMD Radeon RX 6600 XT", '
        '"Card Model": "0x73ff", '
        '"Card Vendor": "Advanced Micro Devices, Inc. [AMD/ATI]", '
        '"Card SKU": "N/A", '
        '"Subsystem ID": "0x6501", '
        '"Device Rev": "0xc1", '
        '"Node ID": "1", '
        '"GUID": "59111", '
        '"GFX Version": "gfx1032"}}'
    )

    with (
        patch(
            "marimo._server.api.endpoints.health._is_gpu_available",
            return_value="rocm",
        ),
        patch(
            "subprocess.run",
        ) as mock_run,
    ):
        mock_run.return_value.stdout = rocm_output
        mock_run.return_value.stderr = ""
        response = client.get("/api/usage", headers=token_header())
    assert response.status_code == 200
    assert "WARNING" not in response.text
    gpu = response.json()["gpu"]
    assert len(gpu) == 1
    assert gpu[0]["index"] == 0
    assert gpu[0]["name"] == "AMD Radeon RX 6600 XT"
    memory = gpu[0]["memory"]
    assert memory["total"] == 8573157376
    assert memory["used"] == 1069268992
    assert memory["free"] == 8573157376 - 1069268992
    assert memory["percent"] == pytest.approx(1069268992 / 8573157376 * 100)


@with_session(SESSION_ID)
def test_read_code(client: TestClient) -> None:
    response = client.get("/api/status/connections", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["active"] == 1


def test_environment_requires_edit_auth(client: TestClient) -> None:
    response = client.get("/api/environment")
    assert response.status_code == 401, response.text


def test_environment(client: TestClient) -> None:
    expected = {
        "marimo": "1.2.3",
        "editable": False,
        "location": "~/.venv/site-packages/marimo",
        "OS": "Darwin",
        "OS Version": "25.0",
        "Processor": "arm",
        "Python Version": "3.12.9",
        "Locale": "en_US",
        "Binaries": {"Browser": "--", "Node": "v22", "uv": "0.11"},
        "Dependencies": {"click": "8.4.2"},
        "Optional Dependencies": {"pandas": "3.0.0"},
        "Experimental Flags": {},
    }
    with patch(
        "marimo._server.api.endpoints.health.get_system_info",
        return_value=expected,
    ) as get_info:
        response = client.get("/api/environment", headers=token_header())

    assert response.status_code == 200, response.text
    assert response.json() == expected
    get_info.assert_called_once_with(redact_home=True)


def test_usage_without_psutil(client: TestClient) -> None:
    """psutil may not be available on all platforms (e.g. Android/Termux)."""
    import sys

    # Simulate psutil being uninstallable by hiding it from the import system.
    original = sys.modules.get("psutil", None)
    sys.modules["psutil"] = None  # type: ignore[assignment]
    try:
        response = client.get("/api/usage", headers=token_header())
    finally:
        if original is None:
            del sys.modules["psutil"]
        else:
            sys.modules["psutil"] = original

    assert response.status_code == 200, response.text
    body = response.json()
    memory = body["memory"]
    assert memory["total"] is None
    assert memory["available"] is None
    assert memory["used"] is None
    assert memory["free"] is None
    assert memory["percent"] is None
    assert memory["has_cgroup_mem_limit"] is False
    assert body["cpu"]["percent"] is None
    assert body["server"]["memory"] is None
    assert body["kernel"]["memory"] is None

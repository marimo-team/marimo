# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import io
import json
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from click.testing import CliRunner

from marimo._cli.cli import main
from marimo._cli.pair import client, commands


@pytest.mark.parametrize("notebook", [None, "nb/one"])
@pytest.mark.parametrize("pretty", [False, True])
def test_snapshot_reads_one_json_response(
    monkeypatch: pytest.MonkeyPatch, notebook: str | None, pretty: bool
) -> None:
    payload = {
        "cursor": "epoch-1005",
        "events": [{"event": "future.event", "data": {"value": 3}}],
    }
    body = io.BytesIO(json.dumps(payload).encode())
    transport = Mock(return_value=client.EventStream(body, Mock()))
    monkeypatch.setattr(client, "open_response", transport)
    monkeypatch.setattr(
        commands,
        "resolve_host",
        lambda _: client.HostEndpoint(
            "http://localhost:2718/base/api/marimo/v1", "private"
        ),
    )
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "snapshot",
            "--url",
            "http://localhost:2718/base",
            "--types",
            " runtime, execution ",
            *(["--notebook", notebook] if notebook is not None else []),
            *(["--pretty"] if pretty else []),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == payload
    assert (len(result.stdout.splitlines()) > 1) is pretty
    assert "\x1b" not in result.stdout
    request = transport.call_args.kwargs
    path = "/snapshot" if notebook is None else "/notebooks/nb%2Fone/snapshot"
    assert urlsplit(request["url"]).path == "/base/api/marimo/v1" + path
    assert parse_qs(urlsplit(request["url"]).query) == {
        "types": ["runtime,execution"]
    }
    assert request["headers"] == {"Authorization": "Bearer private"}
    assert request["method"] == "GET"
    assert body.closed


@pytest.mark.parametrize(
    "body", [b"not json", b"[]", b'{"cursor": 1, "events": []}']
)
def test_snapshot_rejects_invalid_responses_and_closes(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    response = io.BytesIO(body)
    monkeypatch.setattr(
        client,
        "open_response",
        Mock(return_value=client.EventStream(response, Mock())),
    )
    with pytest.raises(client.PairError, match="invalid snapshot"):
        client.get_snapshot(
            url="http://localhost:2718/api/marimo/v1", token="private"
        )
    assert response.closed


def test_snapshot_rejects_empty_type_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolve = Mock()
    monkeypatch.setattr(commands, "resolve_host", resolve)
    result = CliRunner().invoke(
        main,
        [
            "pair",
            "snapshot",
            "--url",
            "http://localhost:2718",
            "--types",
            "runtime,",
        ],
    )
    assert result.exit_code == 2
    assert "empty entries" in result.stderr
    resolve.assert_not_called()

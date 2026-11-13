# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._cli.pair import target
from marimo._cli.pair.client import (
    AmbiguousNotebookError,
    HostEndpoint,
    PairError,
)
from marimo._cli.pair.discovery import Listing, RunningNotebook
from marimo._cli.pair.target import ExecutionTarget

HOST = HostEndpoint("http://127.0.0.1:2718/base/api/marimo/v1", "local-secret")
NOTEBOOK = RunningNotebook(
    "nb-one",
    "analysis",
    "/work/analysis.py",
    "http://127.0.0.1:2718/base",
    "running",
)


@pytest.mark.parametrize("credential", [None, "explicit-secret"])
def test_notebook_id_resolves_without_a_url(
    monkeypatch: pytest.MonkeyPatch,
    credential: str | None,
) -> None:
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _hosts=None: Listing([NOTEBOOK], []),
    )
    monkeypatch.setattr(target, "resolve_host", lambda _: HOST)
    result = target.resolve_target(
        url=None, session_id=NOTEBOOK.id, token=credential
    )
    assert result == ExecutionTarget(
        NOTEBOOK.url, NOTEBOOK.id, credential or HOST.token, NOTEBOOK.id
    )
    assert "secret" not in repr(result)


@pytest.mark.parametrize("identifier", ["nb-one", "sess-one"])
def test_explicit_credentials_scope_discovery_to_the_requested_server(
    monkeypatch: pytest.MonkeyPatch,
    identifier: str,
) -> None:
    calls: list[dict[str, str | None]] = []

    def sessions(**kwargs: str | None) -> dict[str, dict[str, str]]:
        calls.append(kwargs)
        return {"browser": {"session_id": "sess-one", "notebook_id": "nb-one"}}

    monkeypatch.setattr(target, "list_sessions", sessions)
    monkeypatch.setattr(
        target,
        "find_host",
        lambda _: pytest.fail(
            "Explicit credentials must not use local authentication"
        ),
    )
    assert target.resolve_target(
        url="https://remote", session_id=identifier, token="explicit"
    ) == ExecutionTarget("https://remote", "sess-one", "explicit", "nb-one")
    assert calls == [{"url": "https://remote", "token": "explicit"}]


def test_local_url_uses_catalog_without_editor_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _hosts: Listing([NOTEBOOK], []),
    )
    assert target.resolve_target(
        url=NOTEBOOK.url, session_id=None, token=None
    ) == ExecutionTarget(NOTEBOOK.url, NOTEBOOK.id, HOST.token, NOTEBOOK.id)


@pytest.mark.parametrize(
    "identifier",
    [
        "sess-one",
        "session-1",
        "92a5d2d7-74b1-42f7-9b5d-540bd1a610db",
        "nb-opaque",
    ],
)
def test_explicit_local_session_defers_to_the_selected_server(
    monkeypatch: pytest.MonkeyPatch,
    identifier: str,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target, "list_running_notebooks", lambda _: Listing([NOTEBOOK], [])
    )
    assert target.resolve_target(
        url=NOTEBOOK.url, session_id=identifier, token=None
    ) == ExecutionTarget(NOTEBOOK.url, identifier, HOST.token)


def test_multiple_notebooks_require_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _hosts: Listing(
            [
                NOTEBOOK,
                RunningNotebook(
                    "nb-two",
                    NOTEBOOK.name,
                    NOTEBOOK.path,
                    NOTEBOOK.url,
                    "running",
                ),
            ],
            [],
        ),
    )
    with pytest.raises(AmbiguousNotebookError) as error:
        target.resolve_target(url=NOTEBOOK.url, session_id=None, token=None)
    assert error.value.candidates == ("nb-one", "nb-two")


def test_unknown_id_does_not_select_a_different_notebook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _hosts=None: Listing([NOTEBOOK], []),
    )
    with pytest.raises(PairError, match="No running notebook matches"):
        target.resolve_target(url=None, session_id="nb-old", token=None)


def test_remote_url_keeps_legacy_session_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_kwargs: {
            "browser": {"session_id": "sess-one", "notebook_id": "nb-one"},
        },
    )
    assert target.resolve_target(
        url="https://remote", session_id=None, token="explicit"
    ) == ExecutionTarget("https://remote", "sess-one", "explicit", "nb-one")


@pytest.mark.parametrize("known", [True, False])
def test_url_restricts_notebook_discovery_to_one_local_host(
    monkeypatch: pytest.MonkeyPatch,
    known: bool,
) -> None:
    seen: list[list[HostEndpoint] | None] = []

    def listing(hosts: list[HostEndpoint] | None = None) -> Listing:
        seen.append(hosts)
        assert hosts == [HOST]
        return Listing([NOTEBOOK] if known else [], [])

    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(target, "list_running_notebooks", listing)
    if known:
        assert target.resolve_target(
            url=NOTEBOOK.url,
            notebook_id=NOTEBOOK.id,
            session_id=None,
            token=None,
        ) == ExecutionTarget(
            NOTEBOOK.url, NOTEBOOK.id, HOST.token, NOTEBOOK.id
        )
    else:
        with pytest.raises(PairError, match="No running notebook matches"):
            target.resolve_target(
                url=NOTEBOOK.url,
                notebook_id=NOTEBOOK.id,
                session_id=None,
                token=None,
            )
    assert seen == [[HOST]]


def test_remote_scope_does_not_substitute_an_unrelated_notebook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_: {
            "browser": {"session_id": "sess-other", "notebook_id": "nb-other"},
        },
    )
    with pytest.raises(PairError, match="No running notebook matches"):
        target.resolve_target(
            url="https://remote", session_id="nb-missing", token="explicit"
        )


@pytest.mark.parametrize("selector", ["session_id", "notebook_id"])
@pytest.mark.parametrize("identifier", ["sess-not-a-session", "opaque-id"])
def test_catalog_membership_identifies_notebooks(
    monkeypatch: pytest.MonkeyPatch, selector: str, identifier: str
) -> None:
    notebook = RunningNotebook(
        identifier, NOTEBOOK.name, NOTEBOOK.path, NOTEBOOK.url, "running"
    )
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target, "list_running_notebooks", lambda _: Listing([notebook], [])
    )
    assert target.resolve_target(
        url=NOTEBOOK.url,
        session_id=identifier if selector == "session_id" else None,
        notebook_id=identifier if selector == "notebook_id" else None,
        token=None,
    ) == ExecutionTarget(NOTEBOOK.url, identifier, HOST.token, identifier)


def test_local_session_resolution_does_not_ignore_discovery_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _: Listing([], ["Could not read the catalog."]),
    )
    with pytest.raises(PairError, match="Could not read the catalog"):
        target.resolve_target(
            url=NOTEBOOK.url, session_id="opaque-id", token=None
        )


def test_connect_resolves_local_stable_session_to_notebook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: HOST)
    monkeypatch.setattr(
        target, "list_running_notebooks", lambda _: Listing([NOTEBOOK], [])
    )
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_: {
            "browser": {"session_id": "sess-one", "notebook_id": NOTEBOOK.id}
        },
    )
    resolved = target.resolve_target(
        url=NOTEBOOK.url,
        session_id="sess-one",
        token=None,
        require_notebook=True,
    )
    assert resolved.notebook_id == NOTEBOOK.id
    assert resolved.token == HOST.token


def test_connect_resolves_frontend_proxy_to_discovered_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(target, "find_host", lambda _: None)
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_: {
            "browser": {"session_id": "sess-one", "notebook_id": NOTEBOOK.id}
        },
    )
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _hosts=None: Listing([NOTEBOOK], []),
    )
    monkeypatch.setattr(target, "resolve_host", lambda _: HOST)
    assert target.resolve_target(
        url="http://localhost:3000",
        session_id=NOTEBOOK.id,
        token=None,
        require_notebook=True,
    ) == ExecutionTarget(NOTEBOOK.url, NOTEBOOK.id, HOST.token, NOTEBOOK.id)


def test_connect_does_not_replace_explicit_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target,
        "find_host",
        lambda _: pytest.fail("Must not use private credentials"),
    )
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda: pytest.fail("Must not change server"),
    )
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_: {
            "browser": {"session_id": "sess-one", "notebook_id": NOTEBOOK.id}
        },
    )
    result = target.resolve_target(
        url="http://localhost:3000",
        session_id=NOTEBOOK.id,
        token="explicit",
        require_notebook=True,
    )
    assert result.url == "http://localhost:3000"
    assert result.token == "explicit"


def test_connect_rejects_a_session_without_a_host_notebook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target,
        "list_sessions",
        lambda **_: {"browser": {"session_id": "sess-one"}},
    )
    with pytest.raises(PairError, match="does not expose a host notebook ID"):
        target.resolve_target(
            url="https://remote",
            session_id="sess-one",
            token="explicit",
            require_notebook=True,
        )


def test_connect_does_not_discover_another_host_after_authentication_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(**_: object) -> dict[str, dict[str, str]]:
        raise PairError("Authentication failed")

    monkeypatch.setattr(target, "find_host", lambda _: None)
    monkeypatch.setattr(target, "list_sessions", refused)
    monkeypatch.setattr(
        target,
        "list_running_notebooks",
        lambda _: pytest.fail("Must not switch servers"),
    )
    with pytest.raises(PairError, match="Authentication failed"):
        target.resolve_target(
            url="http://localhost:3000",
            session_id=NOTEBOOK.id,
            token=None,
            require_notebook=True,
        )

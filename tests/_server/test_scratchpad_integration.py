# Copyright 2026 Marimo. All rights reserved.
"""Snapshot tests for what an agent sees when driving code-mode.

``code_mode`` + ``/api/kernel/execute`` are the agent's window into
the notebook: whatever the agent does (run cells, mutate the graph,
trigger reactive cascades, hit state setters) it learns about only
through the SSE stream that endpoint returns. We want explicit
coverage of that surface across the scenarios the agent can reach,
so when the output changes we see it.

The existing in-process ``TestClient`` fixture mocks the scratchpad
stream out entirely, so real kernel timing and cross-process
notification ordering aren't testable there. These tests share one
``marimo edit`` subprocess across the module and drive it through
the full HTTP surface: a websocket for session setup and
``completed-run`` synchronization, ``/api/document/transaction`` to
populate ``session.document`` (required for ``code_mode`` cell
lookup by name), ``/api/kernel/run`` to register and execute cells,
and ``/api/kernel/execute`` to hit the scratchpad. Each test gets a
fresh session via a per-test ``session`` fixture that calls
``/api/kernel/restart_session`` on teardown. The response body is
snapshotted as SSE lines with volatile paths and version-specific
traceback noise scrubbed.

Each test's snapshot encodes the expected SSE output for that
scenario — failure cases land in ``done`` with
``{success: false, output: {mimetype: "text/plain", data: ""}}``;
error detail arrives earlier in the stream as ``stderr`` SSE events.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
import uuid
from typing import TYPE_CHECKING, Any

import msgspec
import pytest
import websockets.sync.client
from inline_snapshot import snapshot

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DocumentChange,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
    return port


def _wait_for_server(
    url: str,
    proc: subprocess.Popen[bytes],
    stderr_path: Path,
    timeout_s: float = 15.0,
) -> None:
    import urllib.request

    def _tail() -> str:
        try:
            return stderr_path.read_text(errors="replace")[-4000:]
        except Exception:
            return ""

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"marimo server exited with code {proc.returncode} "
                f"before becoming ready:\n{_tail()}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:
            time.sleep(0.05)
    raise TimeoutError(
        f"marimo server at {url} did not start in {timeout_s}s:\n{_tail()}"
    )


@pytest.fixture(scope="module")
def _server(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[str, None, None]:
    """One ``marimo edit`` subprocess shared across the module.

    Per-test isolation comes from the ``session`` fixture which uses
    a unique ``session_id`` — each WS connect creates a fresh kernel
    and empty ``session.document``.
    """
    tmp = tmp_path_factory.mktemp("mnb")
    port = _free_port()
    notebook = tmp / "nb.py"
    notebook.write_text("import marimo\napp = marimo.App()\n")

    # Log stderr to a file so the pipe can't deadlock when the process
    # outlives many tests. ``_wait_for_server`` tails this on failure.
    stderr_path = tmp / "marimo-stderr.log"
    stderr_file = stderr_path.open("wb")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "marimo",
                "edit",
                str(notebook),
                "--headless",
                "--no-token",
                "--no-skew-protection",
                "--port",
                str(port),
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_for_server(base, proc, stderr_path)
            yield base
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    finally:
        stderr_file.close()


class _Session:
    """Per-test session: unique ID → fresh kernel + empty document.

    Wraps the websocket + HTTP calls. Use ``wait_for_completed_run`` to
    synchronize with kernel activity instead of sleeping.
    """

    def __init__(self, base: str) -> None:
        self.base = base
        self.session_id = f"it_{uuid.uuid4().hex[:8]}"
        self.ws = websockets.sync.client.connect(
            f"{base.replace('http', 'ws')}/ws?session_id={self.session_id}",
            open_timeout=5,
        )
        # Drain kernel-ready handshake.
        self._recv_until(lambda m: m.get("op") == "kernel-ready")

    def close(self) -> None:
        # Close the session on the server via ``restart_session`` —
        # marimo otherwise treats a new WS connection with a new
        # ``session_id`` as a reconnection and keeps the kernel state.
        # This tears down only our session, not the module-wide server.
        try:
            self._post("/api/kernel/restart_session", {})
        except Exception:
            pass
        try:
            self.ws.close()
        except Exception:
            pass

    def _recv_until(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout_s: float = 10.0,
    ) -> dict[str, Any]:
        """Drain WS until a message matches ``predicate(msg)``."""
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("websocket predicate never satisfied")
            raw = self.ws.recv(timeout=remaining)
            msg: dict[str, Any] = json.loads(raw)
            if predicate(msg):
                return msg

    def wait_for_completed_run(self, timeout_s: float = 10.0) -> None:
        """Block until the kernel broadcasts a ``completed-run`` event."""
        self._recv_until(
            lambda m: m.get("op") == "completed-run",
            timeout_s=timeout_s,
        )

    def _post(self, path: str, body: dict[str, Any]) -> str:
        import urllib.request

        req = urllib.request.Request(
            f"{self.base}{path}",
            method="POST",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Marimo-Session-Id": self.session_id,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            text: str = resp.read().decode()
        return text

    def apply_changes(self, changes: list[DocumentChange]) -> None:
        """POST a document transaction built from typed change objects."""
        self._post(
            "/api/document/transaction",
            {"changes": msgspec.to_builtins(changes)},
        )

    def run_cells(self, cell_ids: list[str], codes: list[str]) -> None:
        """Register + run cells in the kernel graph, then wait for idle."""
        self._post(
            "/api/kernel/run",
            {"cellIds": cell_ids, "codes": codes},
        )
        self.wait_for_completed_run()

    def setup_cells(
        self,
        cell_ids: list[str],
        codes: list[str],
        names: list[str] | None = None,
    ) -> None:
        """Register cells in both ``session.document`` and the kernel graph.

        ``/api/kernel/run`` only touches the graph; ``ctx.edit_cell`` /
        ``ctx.run_cell`` in code_mode look up cells from
        ``session.document``, which is kept in sync via document
        transactions from the frontend. We emulate the frontend with
        typed ``CreateCell`` changes.
        """
        if names is None:
            names = cell_ids
        self.apply_changes(
            [
                CreateCell(
                    cell_id=CellId_t(cid),
                    code=code,
                    name=name,
                    config=CellConfig(),
                )
                for cid, code, name in zip(cell_ids, codes, names, strict=True)
            ]
        )
        self.run_cells(cell_ids, codes)

    def execute(self, code: str) -> list[str]:
        """Run ``code`` via /api/kernel/execute; return normalized SSE lines."""
        body = self._post("/api/kernel/execute", {"code": code})
        return _normalize(body)


# Scrub traceback noise that varies across Python versions and platforms.
# ``body`` contains JSON-encoded traceback strings where ``\n`` renders as
# the two-character sequence ``\\n`` (backslash + n), and Windows path
# separators render as ``\\\\`` (two backslashes).
_PATH_RE = re.compile(
    # macOS: /var/folders/... or /tmp/...
    r"/(?:var/folders|tmp)/[^\"\s\\]+"
    # Windows: C:\\\\... up to the closing \\"
    r"|[A-Z]:(?:\\\\[^\"\\]+)+"
)
# Absolute paths into the running marimo source tree — present in
# tracebacks that traverse library frames (e.g. code_mode RuntimeError).
# Match both Unix (``/…/marimo/…py``) and Windows (``C:\\…\\marimo\\…py``)
# forms, reduce the repo-prefix portion to a stable ``<marimo>`` marker, and
# slash-normalize the captured tail so the snapshot compares equal across
# platforms.  Run before ``_PATH_RE`` so Windows source paths are claimed
# here rather than scrubbed to ``<tmp>``.
_MARIMO_SRC_RE = re.compile(
    r'\\"'
    r"(?:"
    r"/(?:[^\"\\]|\\\\)*/"  # Unix prefix: /…/
    r"|[A-Z]:\\\\(?:(?:[^\"\\]|\\\\)*\\\\)?"  # Windows prefix: C:\\(…\\)?
    r")"
    r"(marimo(?:/|\\\\)(?:[^\"\\]|\\\\)*?\.py)"  # marimo<sep>…<file>.py
    r'\\"'
)


def _marimo_src_repl(m: re.Match[str]) -> str:
    return '\\"<marimo>/' + m.group(1).replace("\\\\", "/") + '\\"'


# Error-pointer line (Python 3.11+): indented PEP 657 location underline.
# Python emits this in two flavors: ``~~~^~~~`` (call-site, with tildes
# flanking the carets) and ``^^^^`` (pure multi-caret spans, e.g. an
# expression range). Absent on 3.10, so we strip both for cross-version
# parity. Single-caret pointers (`        ^`) come from the classic
# SyntaxError source-position marker, which is present on all versions,
# so we don't strip them.
_POINTER_RE = re.compile(r" +(?:~+\^+~*|\^{2,})\\n")
# Python 3.13's collapsed-frames view keeps the closing ``)`` on its own
# line for multi-line ``raise Foo(...)`` after ``_COLLAPSED_FRAMES_RE``
# elides the middle; 3.10–3.12 don't show it at all. Strip the lone
# closer for cross-version parity.
_RAISE_CLOSING_PAREN_RE = re.compile(r"(raise \w+\(\\n) +\)\\n")
# Internal marimo frames (e.g. ``File "<tmp>", line 138, in execute_cell``)
# that Py 3.10 shows but 3.11+ hides. Strip them so tests only match the
# user-facing ``<module>`` frame.
_INTERNAL_FRAME_RE = re.compile(
    r'  File \\"<tmp>\\", line \d+, in (?!<module>)[^\\]+\\n'
    r" +[^\\]*\\n"
)
# Python 3.13 collapsed traceback marker (``...<N lines>...``) that older
# Python versions don't emit. Strip together with the indent and newline.
_COLLAPSED_FRAMES_RE = re.compile(r" +\.\.\.<\d+ lines>\.\.\.\\n")
# Line numbers inside internal marimo frames (``File \"<marimo>/..., line N``)
# drift when library source edits shift offsets. Zero them out so the test
# stays stable under unrelated edits to code_mode, runtime, etc.  User-facing
# ``<tmp>`` frames keep their linenos so scratch-cell line positions remain
# assertable.
_MARIMO_FRAME_LINENO_RE = re.compile(r'(File \\"<marimo>/[^\\]*\\"), line \d+')
# Auto-generated cell IDs from ``CellIdGenerator``: 4 random ascii
# letters, appearing in code_mode summaries as ``cell 'AbCd'``. Replace
# with ``cell '<cid>'``.  Scoped to the ``cell '...'`` phrase so
# unrelated 4-letter tokens (e.g. ``'boom'`` inside a test payload) are
# untouched.
_AUTO_CELL_ID_RE = re.compile(r"(cell )'[A-Za-z]{4}'")


def _normalize(body: str) -> list[str]:
    body = _MARIMO_SRC_RE.sub(_marimo_src_repl, body)
    body = _PATH_RE.sub("<tmp>", body)
    body = _POINTER_RE.sub("", body)
    body = _INTERNAL_FRAME_RE.sub("", body)
    body = _COLLAPSED_FRAMES_RE.sub("", body)
    body = _RAISE_CLOSING_PAREN_RE.sub(r"\1", body)
    body = _MARIMO_FRAME_LINENO_RE.sub(r"\1, line N", body)
    body = _AUTO_CELL_ID_RE.sub(r"\1'<cid>'", body)
    return body.splitlines()


@pytest.fixture
def session(_server: str) -> Generator[_Session, None, None]:
    s = _Session(_server)
    try:
        yield s
    finally:
        s.close()


# -- Tests --------------------------------------------------------------


def test_scratchpad_success(session: _Session) -> None:
    """Plain successful scratchpad — regression guard for the happy path."""
    lines = session.execute("1 + 1")

    assert lines == snapshot(
        [
            "event: done",
            (
                'data: {"success": true, "output": '
                '{"mimetype": "text/html", "data": '
                "\"<pre class='text-xs'>2</pre>\"}}"
            ),
            "",
        ]
    )


def test_scratchpad_compile_error(session: _Session) -> None:
    """Scratchpad code that fails to compile (SyntaxError).

    Guards that compile-time errors reach the client with actionable
    detail. Compile failures never go through ``redirect_streams`` /
    ``write_traceback`` (the cell never runs), so the diagnostic has
    to be emitted explicitly as a ``stderr`` SSE event before ``done``.
    """
    lines = session.execute("def :")

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "line 1\\n    def :\\n        ^\\nSyntaxError: invalid syntax\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_scratchpad_itself_errors(session: _Session) -> None:
    """Scratchpad code raises — scratch cell's own error surfaces.

    Regression guard for the working path.
    """
    lines = session.execute("raise ValueError('boom')")

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 1, in <module>\\n'
                "    raise ValueError('boom')\\n"
                'ValueError: boom\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_state_setter_cascade_error(session: _Session) -> None:
    """Scratchpad calls ``set_x(0)`` → downstream cell_b divides by zero.

    Issue #9255 scenario 1. ``state_updates`` flush happens after scratch
    cell goes idle, so the listener sentinel fires before cell_b's
    MARIMO_ERROR arrives. Currently fails on main — the ``done`` event
    says ``success: true`` and the cascade error is silent.
    """
    # cell_b sleeps past the listener's 50ms grace window so its
    # reactive re-run completes AFTER ``stream()`` returns — that's
    # the window in which the bug manifests.
    session.setup_cells(
        ["cell_a", "cell_b"],
        [
            "import marimo as mo\nget_x, set_x = mo.state(1)",
            ("import time\ntime.sleep(0.1)\nresult = 1 / get_x()\nresult"),
        ],
    )

    lines = session.execute("set_x(0)")

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 3, in <module>\\n'
                "    result = 1 / get_x()\\n"
                'ZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_state_chain_cascade_error(session: _Session) -> None:
    """Nested state chain: ``set_x(0)`` → cell_b calls ``set_y`` →
    slow cell_d divides by zero. Listener must capture cell_d's error
    two state-update hops away.
    """
    session.setup_cells(
        ["cell_a", "cell_b", "cell_d"],
        [
            (
                "import marimo as mo\n"
                "get_x, set_x = mo.state(1)\n"
                "get_y, set_y = mo.state(1)"
            ),
            "set_y(get_x())\nok = get_x()",
            "import time\ntime.sleep(0.1)\nz = 1 / get_y()\nz",
        ],
    )

    lines = session.execute("set_x(0)")

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 3, in <module>\\n'
                "    z = 1 / get_y()\\n"
                'ZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_multiple_downstream_cells_all_error(session: _Session) -> None:
    """Two downstream cells both error (fast + slow). Both must be
    reported — partial reporting misleads the agent into thinking
    fixing one error fixes the whole problem.
    """
    session.setup_cells(
        ["cell_a", "cell_b", "cell_c"],
        [
            "import marimo as mo\nget_x, set_x = mo.state(1)",
            "result = 1 / get_x()\nresult",
            (
                "import time\ntime.sleep(0.15)\n"
                "result_c = 100 / get_x()\nresult_c"
            ),
        ],
    )

    lines = session.execute("set_x(0)")

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 1, in <module>\\n'
                "    result = 1 / get_x()\\n"
                'ZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 3, in <module>\\n'
                "    result_c = 100 / get_x()\\n"
                'ZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_scratchpad_raises_after_triggering_cascade(
    session: _Session,
) -> None:
    """Scratchpad calls ``set_x(0)`` (slow cascade) then ``raise``.

    Both the scratch error AND the cascade error should be visible —
    currently only the scratch error surfaces, so the agent sees the
    scratchpad error but not that a downstream cell is also broken.
    """
    session.setup_cells(
        ["cell_a", "cell_b"],
        [
            "import marimo as mo\nget_x, set_x = mo.state(1)",
            ("import time\ntime.sleep(0.1)\nresult = 1 / get_x()\nresult"),
        ],
    )

    lines = session.execute(
        "set_x(0)\nraise RuntimeError('scratch explosion')"
    )

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 2, in <module>\\n'
                "    raise RuntimeError('scratch explosion')\\n"
                'RuntimeError: scratch explosion\\n"}'
            ),
            "",
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n'
                '  File \\"<tmp>\\", line 3, in <module>\\n'
                "    result = 1 / get_x()\\n"
                'ZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_ctx_run_cell_cascade_error(session: _Session) -> None:
    """``ctx.edit_cell + ctx.run_cell`` on cell_a triggers cell_b to
    reactively re-run and error (issue #9255 scenario 2).

    Goes through ``_apply_ops`` which awaits ``_run_cells``
    synchronously — the listener sees the downstream error before the
    sentinel fires. Regression guard for the working path.
    """
    session.setup_cells(
        ["cell_a", "cell_b"],
        [
            "x = 1",
            "import time\ntime.sleep(0.1)\nresult = 1 / x\nresult",
        ],
    )

    lines = session.execute(
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        '    ctx.edit_cell("cell_a", code="x = 0")\n'
        '    ctx.run_cell("cell_a")',
    )

    assert lines == snapshot(
        [
            "event: stderr",
            (
                'data: {"data": "Traceback (most recent call last):\\n  File \\"<tmp>\\", line 3, in <module>\\n    result = 1 / x\\nZeroDivisionError: division by zero\\n"}'
            ),
            "",
            "event: stdout",
            (
                'data: {"data": "edited code of cell \'cell_a\''
                ' (cell_a) and ran\\n"}'
            ),
            "",
            "event: done",
            (
                'data: {"success": false, "output": '
                '{"mimetype": "text/plain", "data": ""}}'
            ),
            "",
        ]
    )


def test_ctx_create_cell_multiply_defined(session: _Session) -> None:
    """``ctx.create_cell`` introducing a duplicate definition errors early.

    The notebook already has ``x = 10`` in ``cell_a``. code_mode's
    dry-run compile detects the new cell would multiply-define ``x``
    and raises ``RuntimeError`` before any real mutation — the new
    cell is never registered and ``x`` stays ``10``.
    """
    session.setup_cells(["cell_a"], ["x = 10"])

    lines = session.execute(
        "import marimo._code_mode as cm\n"
        "async with cm.get_context() as ctx:\n"
        '    ctx.create_cell("x = 20")',
    )

    assert lines == snapshot(
        [
            "event: stderr",
            'data: {"data": "Traceback (most recent call last):\\n  File \\"<marimo>/marimo/_runtime/executor.py\\", line N, in execute_cell_async\\n    await eval(cell.body, glbls)\\n  File \\"<tmp>\\", line 2, in <module>\\n    async with cm.get_context() as ctx:\\n  File \\"<marimo>/marimo/_code_mode/_context.py\\", line N, in __aexit__\\n    self._dry_run_compile(ops)\\n  File \\"<marimo>/marimo/_code_mode/_context.py\\", line N, in _dry_run_compile\\n    raise RuntimeError(\\nRuntimeError: Multiply-defined names:\\n  - \'x\' is already defined in cell \'cell_a\' (cell_a)\\n\\nTo skip validation, use: async with cm.get_context(skip_validation=True) as ctx\\n"}',
            "",
            "event: done",
            'data: {"success": false, "output": {"mimetype": "text/plain", "data": ""}}',
            "",
        ]
    )


def test_ctx_create_cell_skip_validation(session: _Session) -> None:
    """``skip_validation=True`` bypasses the dry-run compile check.

    Same setup as above, but the caller opts out of validation — no
    ``RuntimeError`` is raised and the new cell is registered, as
    evidenced by the ``created cell`` stdout summary. The kernel's own
    graph-validity pass still flags the resulting multiply-defined
    state (visible to the listener as a child error, hence
    ``success: false``), but no traceback reaches stderr because the
    new cell never runs — the error is a pure graph-state marker.
    """
    session.setup_cells(["cell_a"], ["x = 10"])

    lines = session.execute(
        "import marimo._code_mode as cm\n"
        "async with cm.get_context(skip_validation=True) as ctx:\n"
        '    ctx.create_cell("x = 20")',
    )

    assert lines == snapshot(
        [
            "event: stdout",
            'data: {"data": "created cell \'<cid>\'\\n"}',
            "",
            "event: done",
            'data: {"success": false, "output": {"mimetype": "text/plain", "data": ""}}',
            "",
        ]
    )

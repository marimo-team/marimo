from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import pytest

from marimo import __version__
from marimo._ast.cell import CellConfig, RuntimeStateType
from marimo._ast.cell_manager import CellManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import MarimoExceptionRaisedError, UnknownError
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._messaging.notification import CellNotification
from marimo._runtime.commands import ExecuteCellsCommand
from marimo._schemas.session import NotebookSessionV1
from marimo._session.state.serialize import (
    SessionCacheKey,
    SessionCacheManager,
    SessionCacheWriter,
    _hash_code,
    _references_virtual_file,
    deserialize_session,
    get_session_cache_file,
    serialize_notebook,
    serialize_session_view,
)
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

CELL1 = CellId_t("cell1")
CELL2 = CellId_t("cell2")


def _make_document(*cell_ids: CellId_t) -> NotebookDocument:
    """Create a NotebookDocument with the given cell IDs."""
    return NotebookDocument(
        [
            NotebookCell(id=cid, code="", name="__", config=CellConfig())
            for cid in cell_ids
        ]
    )


def _make_cell_notification(
    cell_id: CellId_t,
    *,
    output: CellOutput | None = None,
    status: RuntimeStateType = "idle",
    console: list[CellOutput] | None = None,
) -> CellNotification:
    """Create a CellNotification with sensible defaults."""
    return CellNotification(
        cell_id=cell_id,
        status=status,
        output=output,
        console=console or [],
        timestamp=0,
    )


def _build_code_hash_to_cell_id_mapping(
    session: NotebookSessionV1,
) -> dict[str, CellId_t]:
    """Helper to build code_hash to cell_id mapping for tests."""
    mapping: dict[str, CellId_t] = {}
    for cell in session["cells"]:
        if cell["code_hash"] is not None:
            mapping[cell["code_hash"]] = CellId_t(cell["id"])
    return mapping


def test_serialize_basic_session(session_view: SessionView):
    """Test serialization of a basic session with a single cell with data output"""
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="Hello, world!",
        ),
    )
    view.last_executed_code[CELL1] = "print('Hello, world!')"

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )
    snapshot("basic_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_error(session_view: SessionView):
    """Test serialization of a session with an error output"""
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=[UnknownError(msg="Something went wrong")],
        ),
    )
    view.last_executed_code[CELL1] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )
    snapshot("error_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_console(session_view: SessionView):
    """Test serialization of a session with console output"""
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        console=[
            CellOutput(
                channel=CellChannel.STDOUT,
                mimetype="text/plain",
                data="stdout message",
            ),
            CellOutput(
                channel=CellChannel.STDERR,
                mimetype="text/plain",
                data="stderr message",
            ),
        ],
    )
    view.last_executed_code[CELL1] = "print('test')"

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )
    snapshot("console_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_mime_bundle(session_view: SessionView):
    """Test serialization of a session with a mime bundle output"""
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="application/vnd.marimo+mimebundle",
            data={
                "text/plain": "Hello",
                "text/html": "<b>Hello</b>",
            },
        ),
    )
    view.last_executed_code[CELL1] = "HTML('Hello')"

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )
    snapshot("mime_bundle_session.json", json.dumps(result, indent=2))


def test_serialize_notebook_basic(session_view: SessionView):
    """Test serialization of a SessionView to a Notebook with basic cell"""
    view = session_view
    cell_manager = CellManager()

    cell_manager.register_cell(
        cell_id=CELL1,
        code="print('Hello, world!')",
        name="my_cell",
        config=CellConfig(column=1, disabled=False, hide_code=True),
    )

    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="Hello, world!",
        ),
    )
    view.last_executed_code[CELL1] = "print('Hello, world!')"

    result = serialize_notebook(view, cell_manager)

    assert result["version"] == "1"
    assert result["metadata"]["marimo_version"] == __version__
    assert len(result["cells"]) == 1

    cell = result["cells"][0]
    assert cell["id"] == "cell1"
    assert cell["code"] == "print('Hello, world!')"
    assert cell["name"] == "my_cell"
    assert cell["config"]["column"] == 1
    assert cell["config"]["disabled"] is False
    assert cell["config"]["hide_code"] is True


def test_serialize_notebook_multiple_cells(session_view: SessionView):
    """Test serialization of a SessionView to a Notebook with multiple cells"""
    view = session_view
    cell_manager = CellManager()

    cell_manager.register_cell(
        cell_id=CELL1,
        code="x = 1",
        name="setup",
        config=CellConfig(column=0, disabled=False),
    )

    cell_manager.register_cell(
        cell_id=CELL2,
        code="print(x + 1)",
        name="output",
        config=CellConfig(column=1, hide_code=True),
    )

    view.cell_notifications[CELL1] = _make_cell_notification(CELL1)
    view.last_executed_code[CELL1] = "x = 1"

    view.cell_notifications[CELL2] = _make_cell_notification(
        CELL2,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="2",
        ),
    )
    view.last_executed_code[CELL2] = "print(x + 1)"

    result = serialize_notebook(view, cell_manager)

    assert len(result["cells"]) == 2

    cell1 = result["cells"][0]
    assert cell1["id"] == "cell1"
    assert cell1["code"] == "x = 1"
    assert cell1["name"] == "setup"
    assert cell1["config"]["column"] == 0
    assert cell1["config"]["disabled"] is False

    cell2 = result["cells"][1]
    assert cell2["id"] == "cell2"
    assert cell2["code"] == "print(x + 1)"
    assert cell2["name"] == "output"
    assert cell2["config"]["column"] == 1
    assert cell2["config"]["hide_code"] is True


def test_serialize_notebook_multiple_cells_not_top_down(
    session_view: SessionView,
):
    """Test serializing an "out-of-order" notebook.

    Serialize a notebook in which the topological sort
    is different from the notebook order. Make sure
    the serialized notebook is in notebook order.
    """

    view = session_view
    cell_manager = CellManager()

    cell_manager.register_cell(
        cell_id=CELL1,
        code="print(x + 1)",
        name="output",
        config=CellConfig(column=1, hide_code=True),
    )

    cell_manager.register_cell(
        cell_id=CELL2,
        code="x = 2",
        name="setup",
        config=CellConfig(column=0, disabled=False),
    )

    view.cell_notifications[CELL2] = _make_cell_notification(CELL2)
    view.last_executed_code[CELL2] = "x = 1"

    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="2",
        ),
    )
    view.last_executed_code[CELL1] = "print(x + 1)"

    result = serialize_notebook(view, cell_manager)

    assert len(result["cells"]) == 2

    cell1 = result["cells"][0]
    assert cell1["id"] == "cell1"
    assert cell1["code"] == "print(x + 1)"
    assert cell1["name"] == "output"
    assert cell1["config"]["column"] == 1
    assert cell1["config"]["hide_code"] is True

    cell2 = result["cells"][1]
    assert cell2["id"] == "cell2"
    assert cell2["code"] == "x = 1"
    assert cell2["name"] == "setup"
    assert cell2["config"]["column"] == 0
    assert cell2["config"]["disabled"] is False


def test_serialize_notebook_empty_code(session_view: SessionView):
    """Test serialization when cells have no executed code"""
    view = session_view
    cell_manager = CellManager()

    cell_manager.register_cell(
        cell_id=CELL1,
        code="# Original code",
        name="empty_cell",
        config=CellConfig(),
    )

    # Add to session view but without executed code
    view.cell_notifications[CELL1] = _make_cell_notification(CELL1)
    # No entry in last_executed_code

    result = serialize_notebook(view, cell_manager)

    assert len(result["cells"]) == 1
    cell = result["cells"][0]
    assert cell["id"] == "cell1"
    assert (
        cell["code"] == ""
    )  # Should default to empty string from last_executed_code
    assert cell["name"] == "empty_cell"
    assert cell["config"]["column"] is None
    assert cell["config"]["disabled"] is False  # Default value
    assert cell["config"]["hide_code"] is False  # Default value


def test_serialize_notebook_no_cells(session_view: SessionView):
    """Test serialization of an empty SessionView"""
    view = session_view
    cell_manager = CellManager()

    result = serialize_notebook(view, cell_manager)

    assert result["version"] == "1"
    assert result["metadata"]["marimo_version"] == __version__
    assert len(result["cells"]) == 0


# TODO(akshayka): Reconcile this test with
# https://github.com/marimo-team/marimo/pull/5377. It appears we
# need to serialize notebook based on the cell manager not
# session view in order to get correct ordering of cells.
@pytest.mark.xfail(
    reason="Unclear how to serialize a notebook when "
    "the cell manager's view of cells differs from the session view. "
    "The session view doesn't know the order of cells in the notebook."
)
def test_serialize_notebook_missing_cell_data(session_view: SessionView):
    """Test serialization when cell exists in SessionView but not in CellManager"""
    view = session_view
    cell_manager = CellManager()

    # Add cell to session view but don't register it with cell manager
    cell_id = CellId_t("orphan_cell")
    view.cell_notifications[cell_id] = _make_cell_notification(
        cell_id,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="orphan output",
        ),
    )
    view.last_executed_code[cell_id] = "print('orphan')"

    result = serialize_notebook(view, cell_manager)

    assert len(result["cells"]) == 1
    cell = result["cells"][0]
    assert cell["id"] == "orphan_cell"
    assert cell["code"] == "print('orphan')"
    assert cell["name"] is None  # Should be None due to missing cell data
    assert cell["config"]["column"] is None
    assert cell["config"]["disabled"] is None
    assert cell["config"]["hide_code"] is None


def test_session_round_trip_drops_dangling_virtual_file_urls(
    session_view: SessionView,
):
    # Regression: https://github.com/marimo-team/marimo/issues/9273.
    # A `./@file/...` URL in cached HTML output points at a per-process
    # buffer that won't exist on the next kernel; the URL must not
    # survive the on-disk cache round-trip.
    html = (
        '<marimo-anywidget data-name="Counter">'
        '<img src="./@file/4-abcd1234.png">'
        "</marimo-anywidget>"
    )
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data=html,
        ),
    )
    view.last_executed_code[CELL1] = "widget"

    serialized = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=True
    )
    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(serialized)
    restored = deserialize_session(serialized, code_hash_to_cell_id)

    assert restored.cell_notifications[CELL1].output is None


def test_session_round_trip_drops_nested_virtual_file_urls(
    session_view: SessionView,
):
    # `_references_virtual_file` recurses through dicts and lists — a mime
    # bundle where only one alternative carries the `./@file/` URL must
    # still trigger the drop.
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="application/vnd.marimo+mimebundle",
            data={
                "text/plain": "widget",
                "text/html": '<img src="./@file/4-abcd1234.png">',
            },
        ),
    )
    view.last_executed_code[CELL1] = "widget"

    serialized = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=True
    )
    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(serialized)
    restored = deserialize_session(serialized, code_hash_to_cell_id)

    assert restored.cell_notifications[CELL1].output is None


def test_drop_virtual_file_outputs_ignores_literal_prefix_in_text(
    session_view: SessionView,
):
    # The check is anchored to the full URL shape (`./@file/<digits>-`),
    # so plain text that happens to mention the prefix must not trigger
    # the drop.
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="marimo stores virtual files under ./@file/ on the server",
        ),
    )
    view.last_executed_code[CELL1] = "print('docs')"

    serialized = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=True
    )
    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(serialized)
    restored = deserialize_session(serialized, code_hash_to_cell_id)

    restored_output = restored.cell_notifications[CELL1].output
    assert restored_output is not None
    assert restored_output.data == (
        "marimo stores virtual files under ./@file/ on the server"
    )


def test_references_virtual_file_handles_cyclic_data():
    # A self-referencing dict or list must return False cleanly rather
    # than raising RecursionError — the check is purely defensive, but
    # a serializer that blows the stack is a poor failure mode for code
    # that just decides whether to drop URLs.
    cyclic_dict: dict[str, object] = {}
    cyclic_dict["self"] = cyclic_dict
    assert _references_virtual_file(cyclic_dict) is False

    cyclic_list: list[object] = []
    cyclic_list.append(cyclic_list)
    assert _references_virtual_file(cyclic_list) is False

    # Cycle through a nested structure still detects the URL when present.
    leaf: dict[str, object] = {"html": '<img src="./@file/4-abcd1234.png">'}
    leaf["self"] = leaf
    assert _references_virtual_file(leaf) is True


def test_drop_virtual_file_outputs_preserves_unrelated_outputs(
    session_view: SessionView,
):
    # The drop is targeted: outputs without a virtual-file URL must pass
    # through even when `drop_virtual_file_outputs=True`.
    view = session_view
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/html",
            data="<b>Hello</b>",
        ),
    )
    view.last_executed_code[CELL1] = "HTML('Hello')"

    serialized = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=True
    )
    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(serialized)
    restored = deserialize_session(serialized, code_hash_to_cell_id)

    restored_output = restored.cell_notifications[CELL1].output
    assert restored_output is not None
    assert restored_output.data == "<b>Hello</b>"


def test_deserialize_basic_session():
    """Test deserialization of a basic session"""
    session = NotebookSessionV1(
        version="1",
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [
                    {
                        "type": "data",
                        "data": {"text/plain": "Hello, world!"},
                    }
                ],
                "console": [],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert CellId_t("cell1") in view.cell_notifications
    cell = view.cell_notifications[CellId_t("cell1")]
    assert cell.output is not None
    assert cell.output.channel == CellChannel.OUTPUT
    assert cell.output.mimetype == "text/plain"
    assert cell.output.data == "Hello, world!"


def test_deserialize_session_with_error():
    """Test deserialization of a session with an error"""
    session = NotebookSessionV1(
        version=1,
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [
                    {
                        "type": "error",
                        "ename": "RuntimeError",
                        "evalue": "Something went wrong",
                        "traceback": [],
                    }
                ],
                "console": [],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "cell1" in view.cell_notifications
    cell = view.cell_notifications["cell1"]
    assert cell.output is not None
    assert cell.output.channel == CellChannel.MARIMO_ERROR
    assert cell.output.mimetype == "application/vnd.marimo+error"
    assert isinstance(cell.output.data, list)
    error = cell.output.data[0]
    assert isinstance(error, MarimoExceptionRaisedError)
    assert error.msg == "Something went wrong"


def test_deserialize_session_with_console():
    """Test deserialization of a session with console output"""
    session = NotebookSessionV1(
        version=1,
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [],
                "console": [
                    {
                        "type": "stream",
                        "name": "stdout",
                        "text": "stdout message",
                    },
                    {
                        "type": "stream",
                        "name": "stderr",
                        "text": "stderr message",
                    },
                ],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "cell1" in view.cell_notifications
    cell = view.cell_notifications["cell1"]
    assert isinstance(cell.console, list)
    assert len(cell.console) == 2
    console_outputs = cell.console
    assert console_outputs[0].channel == CellChannel.STDOUT
    assert console_outputs[0].data == "stdout message"
    assert console_outputs[0].mimetype == "text/plain"
    assert console_outputs[1].channel == CellChannel.STDERR
    assert console_outputs[1].data == "stderr message"
    assert console_outputs[1].mimetype == "text/plain"


async def test_session_cache_writer(session_view: SessionView):
    """Test AsyncWriter writes session data periodically"""
    view = session_view
    doc = _make_document(CELL1)
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="test data",
        ),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.json"
        writer = SessionCacheWriter(view, doc, path, interval=0.1)

        # Start writer and wait for first write
        writer.start()
        await asyncio.sleep(0.2)

        # Verify data was written
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["cells"]) == 1
        assert data["cells"][0]["id"] == "cell1"

        # Stop writer and verify cleanup
        await writer.stop()


async def test_session_cache_writer_no_writes(session_view: SessionView):
    """Test AsyncWriter does not write when no changes"""
    view = session_view
    doc = _make_document()
    view.mark_auto_export_session()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.json"
        writer = SessionCacheWriter(view, doc, path, interval=0.1)
        writer.start()
        await asyncio.sleep(0.2)
        assert not path.exists()

        view._touch()
        await asyncio.sleep(0.2)
        assert path.exists()

        await writer.stop()


def test_get_session_cache_file():
    is_windows = sys.platform == "win32"
    # Linux path
    if not is_windows:
        path = Path("/path/to/notebook.py")
        cache_file = get_session_cache_file(path)
        assert cache_file == Path(
            "/path/to/__marimo__/session/notebook.py.json"
        )
    else:
        # Windows path
        path = Path("C:\\path\\to\\notebook.py")
        cache_file = get_session_cache_file(path)
        assert cache_file == Path(
            "C:\\path\\to\\__marimo__\\session\\notebook.py.json"
        )


def test_get_session_cache_file_with_pycache_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    prefix = tmp_path / "prefix"
    monkeypatch.setattr("sys.pycache_prefix", str(prefix))

    path = tmp_path / "app" / "notebooks" / "notebook.py"
    cache_file = get_session_cache_file(path)
    relative_parent = Path(*path.parent.parts[1:])  # strip root
    assert cache_file == (
        prefix
        / relative_parent
        / "__marimo__"
        / "session"
        / "notebook.py.json"
    )


def test_hash_code():
    """Test _hash_code function"""
    assert _hash_code(None) is None
    assert _hash_code("print('hello')") == "e73b48e8e00d36304ea7204a0683c814"
    assert _hash_code("") is None


def test_deserialize_mime_bundle():
    """Test deserialization of a session with mime bundle output"""
    session = NotebookSessionV1(
        version=1,
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [
                    {
                        "type": "data",
                        "data": {
                            "text/plain": "Hello",
                            "text/html": "<b>Hello</b>",
                        },
                    }
                ],
                "console": [],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "cell1" in view.cell_notifications
    cell = view.cell_notifications["cell1"]
    assert cell.output is not None
    assert cell.output.channel == CellChannel.OUTPUT
    assert cell.output.mimetype == "application/vnd.marimo+mimebundle"
    assert cell.output.data == {
        "text/plain": "Hello",
        "text/html": "<b>Hello</b>",
    }


def test_deserialize_empty_data():
    """Test deserialization of a session with empty data output"""
    session = NotebookSessionV1(
        version=1,
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [{"type": "data", "data": {}}],
                "console": [],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "cell1" in view.cell_notifications
    cell = view.cell_notifications["cell1"]
    assert cell.output is None


def test_deserialize_error_with_traceback():
    """Test deserialization of a session with an error with a traceback"""
    tb = (
        '<span class="codehilite"><div class="highlight"><pre><span></span>'
        '<span class="gt">Traceback (most recent call last):</span>\n'
        '  File <span class="nb">&quot;/usr/local/lib/python3.12/site-packages/marimo/_runtime/executor.py&quot;</span>, line <span class="m">139</span>, in <span class="n">execute_cell</span>\n'
        '<span class="w">    </span><span class="k">return</span> <span class="nb">eval</span><span class="p">(</span><span class="n">cell</span><span class="o">.</span><span class="n">last_expr</span><span class="p">,</span> <span class="n">glbls</span><span class="p">)</span>\n'
        '<span class="w">           </span><span class="pm">^^^^^^^^^^^^^^^^^^^^^^^^^^^</span>\n'
        '  File <span class="nb">&quot;/tmp/marimo_46/__marimo__cell_eAXK_.py&quot;</span>, line <span class="m">1</span>, in <span class="n">&lt;module&gt;</span>\n'
        '<span class="w">    </span><span class="mi">1</span> <span class="o">/</span> <span class="mi">0</span>\n'
        '<span class="w">    </span><span class="pm">~~^~~</span>\n'
        '<span class="gr">ZeroDivisionError</span>: <span class="n">division by zero</span>\n'
        "</pre></div>\n</span>"
    )

    session = NotebookSessionV1(
        version="1",
        metadata={"marimo_version": "0.14.16"},
        cells=[
            {
                "id": "eAXK",
                "code_hash": "bc650f1a8070e8d0e7c0929302a5d2a6",
                "outputs": [
                    {
                        "type": "error",
                        "ename": "exception",
                        "evalue": "division by zero",
                        "traceback": [],
                    }
                ],
                "console": [
                    {
                        "type": "stream",
                        "name": "stderr",
                        "text": tb,
                    }
                ],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "eAXK" in view.cell_notifications
    cell = view.cell_notifications["eAXK"]
    assert cell.output is not None
    assert cell.output.channel == CellChannel.MARIMO_ERROR
    assert cell.output.mimetype == "application/vnd.marimo+error"
    assert isinstance(cell.output.data, list)
    assert len(cell.output.data) == 1
    error = cell.output.data[0]
    assert isinstance(error, MarimoExceptionRaisedError)
    assert error.msg == "division by zero"
    assert error.exception_type == "exception"
    assert cell.console is not None
    assert isinstance(cell.console, list)
    assert len(cell.console) == 1
    console_output = cell.console[0]
    assert console_output.channel == CellChannel.STDERR
    assert console_output.mimetype == "application/vnd.marimo+traceback"
    assert console_output.data == tb


def test_deserialize_session_with_console_mimetype():
    """Test deserialization of a session with console output that has mimetype"""
    session = NotebookSessionV1(
        version=1,
        metadata={"marimo_version": "1.0.0"},
        cells=[
            {
                "id": "cell1",
                "code_hash": "123",
                "outputs": [],
                "console": [
                    {
                        "type": "stream",
                        "name": "stdout",
                        "text": "stdout message",
                        "mimetype": "text/html",
                    },
                    {
                        "type": "stream",
                        "name": "stderr",
                        "text": "stderr message",
                        "mimetype": "text/plain",
                    },
                ],
            }
        ],
    )

    code_hash_to_cell_id = _build_code_hash_to_cell_id_mapping(session)
    view = deserialize_session(session, code_hash_to_cell_id)
    assert "cell1" in view.cell_notifications
    cell = view.cell_notifications["cell1"]
    assert isinstance(cell.console, list)
    assert len(cell.console) == 2
    console_outputs = cell.console
    assert console_outputs[0].channel == CellChannel.STDOUT
    assert console_outputs[0].data == "stdout message"
    assert console_outputs[0].mimetype == "text/html"
    assert console_outputs[1].channel == CellChannel.STDERR
    assert console_outputs[1].data == "stderr message"
    assert console_outputs[1].mimetype == "text/plain"


def test_serialize_session_with_dict_error():
    """Test serialization of a session with a dictionary error"""
    view = SessionView()
    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=[
                {"type": "unknown", "msg": "Something went wrong"}
            ],  # Dictionary instead of Error object
        ),
    )
    view.last_executed_code[CELL1] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )
    assert len(result["cells"]) == 1
    assert len(result["cells"][0]["outputs"]) == 1
    assert result["cells"][0]["outputs"][0]["type"] == "error"
    assert result["cells"][0]["outputs"][0]["ename"] == "unknown"
    assert result["cells"][0]["outputs"][0]["evalue"] == "Something went wrong"


def test_serialize_session_with_mixed_error_formats(session_view: SessionView):
    """Test serialization of a session with mixed error formats (dict and object)"""
    view = session_view

    # Test with both dictionary and object error formats
    mixed_errors = [
        # Dictionary format error
        {
            "type": "exception",
            "exception_type": "ValueError",
            "msg": "Invalid value",
            "raising_cell": "cell1",
            "traceback": None,
        },
        # Object format error
        UnknownError(msg="Runtime error occurred", error_type="RuntimeError"),
    ]

    view.cell_notifications[CELL1] = _make_cell_notification(
        CELL1,
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=mixed_errors,
        ),
    )
    view.last_executed_code[CELL1] = "# code that causes mixed errors"

    result = serialize_session_view(
        view, cell_ids=[CELL1], drop_virtual_file_outputs=False
    )

    # Verify the error normalization worked correctly
    assert len(result["cells"]) == 1
    cell = result["cells"][0]
    assert len(cell["outputs"]) == 2

    # Check first error (dictionary with explicit no traceback)
    error1 = cell["outputs"][0]
    assert error1["type"] == "error"
    assert error1["ename"] == "exception"
    assert error1["evalue"] == "Invalid value"
    assert error1["traceback"] is None

    # Check second error (object format)
    error2 = cell["outputs"][1]
    assert error2["type"] == "error"
    assert error2["ename"] == "RuntimeError"
    assert error2["evalue"] == "Runtime error occurred"
    assert (
        error2["traceback"] == []
    )  # UnknownError doesn't have traceback by default

    snapshot("mixed_error_session.json", json.dumps(result, indent=2))


class TestSessionCacheManager:
    """Test SessionCacheManager functionality"""

    def test_init_without_path(self, session_view: SessionView):
        """Test initialization without path"""
        view = session_view
        doc = _make_document()
        manager = SessionCacheManager(view, doc, None, 0.1)
        manager.start()
        assert manager.session_cache_writer is None

    async def test_rename_path(self, session_view: SessionView):
        """Test renaming path updates writer"""
        view = session_view
        doc = _make_document()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = Path(tmpdir) / "old.py"
            new_path = Path(tmpdir) / "new.py"

            manager = SessionCacheManager(view, doc, old_path, 0.1)
            manager.start()
            assert manager.session_cache_writer is not None
            old_writer = manager.session_cache_writer

            manager.rename_path(new_path)
            assert manager.session_cache_writer is not None
            assert manager.session_cache_writer != old_writer
            assert manager.path == new_path

    def test_read_session_view_no_path(self, session_view: SessionView):
        """Test reading session view without path"""
        view = session_view
        doc = _make_document()
        manager = SessionCacheManager(view, doc, None, 0.1)
        assert (
            manager.read_session_view(
                SessionCacheKey(codes=(), marimo_version="-1", cell_ids=())
            )
            == view
        )

    def test_read_session_view_no_cache(self, session_view: SessionView):
        """Test reading session view with no cache file"""
        view = session_view
        doc = _make_document()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            manager = SessionCacheManager(view, doc, path, 0.1)
            assert (
                manager.read_session_view(
                    SessionCacheKey(codes=(), marimo_version="-1", cell_ids=())
                )
                == view
            )

    async def test_read_session_view_with_cache(
        self, session_view: SessionView
    ):
        """Test reading session view from cache file"""
        view = session_view
        doc = _make_document(CELL1)
        view.cell_notifications[CELL1] = _make_cell_notification(
            CELL1,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(
                view, cell_ids=[CELL1], drop_virtual_file_outputs=False
            )
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), doc, path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(None,),
                    marimo_version=__version__,
                    cell_ids=(CELL1,),
                )
            )
            assert loaded_view.cell_notifications is not None

    async def test_read_session_view_cache_miss_code(
        self, session_view: SessionView
    ):
        """Test reading session view from cache file"""
        view = session_view
        doc = _make_document(CELL1)
        view.cell_notifications[CELL1] = _make_cell_notification(
            CELL1,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
        )
        view.add_control_request(
            ExecuteCellsCommand(cell_ids=[CELL1], codes=["a"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(
                view, cell_ids=[CELL1], drop_virtual_file_outputs=False
            )
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), doc, path, 0.1)
            loaded_view = manager.read_session_view(
                # foo != a, cache miss
                SessionCacheKey(
                    codes=("foo",),
                    marimo_version=__version__,
                    cell_ids=(CELL1,),
                )
            )
            assert not loaded_view.cell_notifications

    async def test_read_session_view_cache_miss_version(
        self, session_view: SessionView
    ):
        """Test reading session view from cache file"""
        view = session_view
        id1, id2 = CellId_t("1"), CellId_t("2")
        doc = _make_document(id1, id2)
        view.add_control_request(
            ExecuteCellsCommand(cell_ids=[id1, id2], codes=["a", "b"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(
                view, cell_ids=[id1, id2], drop_virtual_file_outputs=False
            )
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), doc, path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(
                        "a",
                        "b",
                    ),
                    marimo_version="-1",
                    cell_ids=(id1, id2),
                )
            )
            assert not loaded_view.cell_notifications

    async def test_read_session_view_cache_miss_script_metadata_hash(
        self, session_view: SessionView
    ):
        """Test reading session view from cache file."""
        view = session_view
        id1, id2 = CellId_t("1"), CellId_t("2")
        doc = _make_document(id1, id2)
        view.add_control_request(
            ExecuteCellsCommand(cell_ids=[id1, id2], codes=["a", "b"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            data = serialize_session_view(
                view,
                cell_ids=[id1, id2],
                script_metadata_hash="old",
                drop_virtual_file_outputs=False,
            )
            cache_file.write_text(json.dumps(data))

            manager = SessionCacheManager(SessionView(), doc, path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(
                        "a",
                        "b",
                    ),
                    marimo_version=__version__,
                    cell_ids=(id1, id2),
                    script_metadata_hash="new",
                )
            )
            assert not loaded_view.cell_notifications

    async def test_read_session_view_cache_hit(
        self, session_view: SessionView
    ):
        """Test reading session view from cache file"""
        view = session_view
        doc = _make_document(CELL1, CELL2)
        test_output = CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="test data",
        )
        view.cell_notifications[CELL1] = _make_cell_notification(
            CELL1, output=test_output
        )
        view.cell_notifications[CELL2] = _make_cell_notification(
            CELL2, output=test_output
        )

        view.add_control_request(
            ExecuteCellsCommand(cell_ids=[CELL1, CELL2], codes=["a", "b"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(
                view, cell_ids=[CELL1, CELL2], drop_virtual_file_outputs=False
            )
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), doc, path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(
                        "a",
                        "b",
                    ),
                    marimo_version=__version__,
                    cell_ids=(CELL1, CELL2),
                )
            )
            # cache hit: codes and version match
            assert len(loaded_view.cell_notifications) == 2

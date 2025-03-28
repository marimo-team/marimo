from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from marimo import __version__
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import MarimoExceptionRaisedError, UnknownError
from marimo._messaging.ops import CellOp
from marimo._runtime.requests import ExecuteMultipleRequest
from marimo._schemas.session import NotebookSessionV1
from marimo._server.session.serialize import (
    SessionCacheKey,
    SessionCacheManager,
    SessionCacheWriter,
    _hash_code,
    deserialize_session,
    get_session_cache_file,
    serialize_session_view,
)
from marimo._server.session.session_view import SessionView
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_serialize_basic_session():
    """Test serialization of a basic session with a single cell with data output"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="Hello, world!",
        ),
        console=[],
        timestamp=0,
    )
    view.last_executed_code["cell1"] = "print('Hello, world!')"

    result = serialize_session_view(view)
    snapshot("basic_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_error():
    """Test serialization of a session with an error output"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=[UnknownError(type="unknown", msg="Something went wrong")],
        ),
        console=[],
        timestamp=0,
    )
    view.last_executed_code["cell1"] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(view)
    snapshot("error_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_console():
    """Test serialization of a session with console output"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=None,
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
        timestamp=0,
    )
    view.last_executed_code["cell1"] = "print('test')"

    result = serialize_session_view(view)
    snapshot("console_session.json", json.dumps(result, indent=2))


def test_serialize_session_with_mime_bundle():
    """Test serialization of a session with a mime bundle output"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="application/vnd.marimo+mimebundle",
            data={
                "text/plain": "Hello",
                "text/html": "<b>Hello</b>",
            },
        ),
        console=[],
        timestamp=0,
    )
    view.last_executed_code["cell1"] = "HTML('Hello')"

    result = serialize_session_view(view)
    snapshot("mime_bundle_session.json", json.dumps(result, indent=2))


def test_deserialize_basic_session():
    """Test deserialization of a basic session"""
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
                        "data": {"text/plain": "Hello, world!"},
                    }
                ],
                "console": [],
            }
        ],
    )

    view = deserialize_session(session)
    assert "cell1" in view.cell_operations
    cell = view.cell_operations["cell1"]
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

    view = deserialize_session(session)
    assert "cell1" in view.cell_operations
    cell = view.cell_operations["cell1"]
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

    view = deserialize_session(session)
    assert "cell1" in view.cell_operations
    cell = view.cell_operations["cell1"]
    assert isinstance(cell.console, list)
    assert len(cell.console) == 2
    console_outputs = cell.console
    assert console_outputs[0].channel == CellChannel.STDOUT
    assert console_outputs[0].data == "stdout message"
    assert console_outputs[1].channel == CellChannel.STDERR
    assert console_outputs[1].data == "stderr message"


async def test_session_cache_writer():
    """Test AsyncWriter writes session data periodically"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="test data",
        ),
        console=[],
        timestamp=0,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.json"
        writer = SessionCacheWriter(view, path, interval=0.1)

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


async def test_session_cache_writer_no_writes():
    """Test AsyncWriter does not write when no changes"""
    view = SessionView()
    view.mark_auto_export_session()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "session.json"
        writer = SessionCacheWriter(view, path, interval=0.1)
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

    view = deserialize_session(session)
    assert "cell1" in view.cell_operations
    cell = view.cell_operations["cell1"]
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

    view = deserialize_session(session)
    assert "cell1" in view.cell_operations
    cell = view.cell_operations["cell1"]
    assert cell.output is None


def test_serialize_session_with_dict_error():
    """Test serialization of a session with a dictionary error"""
    view = SessionView()
    view.cell_operations["cell1"] = CellOp(
        cell_id="cell1",
        status="idle",
        output=CellOutput(
            channel=CellChannel.MARIMO_ERROR,
            mimetype="application/vnd.marimo+error",
            data=[
                {"type": "unknown", "msg": "Something went wrong"}
            ],  # Dictionary instead of Error object
        ),
        console=[],
        timestamp=0,
    )
    view.last_executed_code["cell1"] = (
        "raise RuntimeError('Something went wrong')"
    )

    result = serialize_session_view(view)
    assert len(result["cells"]) == 1
    assert len(result["cells"][0]["outputs"]) == 1
    assert result["cells"][0]["outputs"][0]["type"] == "error"
    assert result["cells"][0]["outputs"][0]["ename"] == "unknown"
    assert result["cells"][0]["outputs"][0]["evalue"] == "Something went wrong"


class TestSessionCacheManager:
    """Test SessionCacheManager functionality"""

    def test_init_without_path(self):
        """Test initialization without path"""
        view = SessionView()
        manager = SessionCacheManager(view, None, 0.1)
        manager.start()
        assert manager.session_cache_writer is None

    async def test_rename_path(self):
        """Test renaming path updates writer"""
        view = SessionView()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = Path(tmpdir) / "old.py"
            new_path = Path(tmpdir) / "new.py"

            manager = SessionCacheManager(view, old_path, 0.1)
            manager.start()
            assert manager.session_cache_writer is not None
            old_writer = manager.session_cache_writer

            manager.rename_path(new_path)
            assert manager.session_cache_writer is not None
            assert manager.session_cache_writer != old_writer
            assert manager.path == new_path

    def test_read_session_view_no_path(self):
        """Test reading session view without path"""
        view = SessionView()
        manager = SessionCacheManager(view, None, 0.1)
        assert (
            manager.read_session_view(
                SessionCacheKey(codes=tuple(), marimo_version="-1")
            )
            == view
        )

    def test_read_session_view_no_cache(self):
        """Test reading session view with no cache file"""
        view = SessionView()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            manager = SessionCacheManager(view, path, 0.1)
            assert (
                manager.read_session_view(
                    SessionCacheKey(codes=tuple(), marimo_version="-1")
                )
                == view
            )

    async def test_read_session_view_with_cache(self):
        """Test reading session view from cache file"""
        view = SessionView()
        view.cell_operations["cell1"] = CellOp(
            cell_id="cell1",
            status="idle",
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
            console=[],
            timestamp=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(view)
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(codes=(None,), marimo_version=__version__)
            )
            assert "cell1" in loaded_view.cell_operations
            cell = loaded_view.cell_operations["cell1"]
            assert cell.output is not None
            assert cell.output.data == "test data"

    async def test_read_session_view_cache_miss_code(self):
        """Test reading session view from cache file"""
        view = SessionView()
        view.cell_operations["cell1"] = CellOp(
            cell_id="cell1",
            status="idle",
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
            console=[],
            timestamp=0,
        )
        view.add_control_request(
            ExecuteMultipleRequest(cell_ids=["cell1"], codes=["a"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(view)
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), path, 0.1)
            loaded_view = manager.read_session_view(
                # foo != a, cache miss
                SessionCacheKey(codes=("foo",), marimo_version=__version__)
            )
            assert not loaded_view.cell_operations

    async def test_read_session_view_cache_miss_version(self):
        """Test reading session view from cache file"""
        view = SessionView()
        view.add_control_request(
            ExecuteMultipleRequest(cell_ids=["1", "2"], codes=["a", "b"])
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(view)
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(
                        "a",
                        "b",
                    ),
                    marimo_version="-1",
                )
            )
            assert not loaded_view.cell_operations

    async def test_read_session_view_cache_hit(self):
        """Test reading session view from cache file"""
        view = SessionView()
        view.cell_operations["cell1"] = CellOp(
            cell_id="cell1",
            status="idle",
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
            console=[],
            timestamp=0,
        )
        view.cell_operations["cell2"] = CellOp(
            cell_id="cell2",
            status="idle",
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="test data",
            ),
            console=[],
            timestamp=0,
        )

        view.add_control_request(
            ExecuteMultipleRequest(
                cell_ids=["cell1", "cell2"], codes=["a", "b"]
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notebook.py"
            cache_file = get_session_cache_file(path)
            cache_file.parent.mkdir(parents=True)

            # Write cache file
            data = serialize_session_view(view)
            cache_file.write_text(json.dumps(data))

            # Read back
            manager = SessionCacheManager(SessionView(), path, 0.1)
            loaded_view = manager.read_session_view(
                SessionCacheKey(
                    codes=(
                        "a",
                        "b",
                    ),
                    marimo_version=__version__,
                )
            )
            # cache hit: codes and version match
            assert len(loaded_view.cell_operations) == 2

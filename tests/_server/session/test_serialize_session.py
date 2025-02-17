from __future__ import annotations

import json

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import MarimoExceptionRaisedError, UnknownError
from marimo._messaging.ops import CellOp
from marimo._schemas.session import NotebookSession
from marimo._server.session.serialize import (
    deserialize_session,
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
            mimetype="text/plain",
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
    session = NotebookSession(
        version="1.0.0",
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
    session = NotebookSession(
        version="1.0.0",
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
    assert isinstance(cell.output.data[0], MarimoExceptionRaisedError)
    assert cell.output.data[0].msg == "Something went wrong"


def test_deserialize_session_with_console():
    """Test deserialization of a session with console output"""
    session = NotebookSession(
        version="1.0.0",
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
    assert len(cell.console) == 2
    assert cell.console[0].channel == CellChannel.STDOUT
    assert cell.console[0].data == "stdout message"
    assert cell.console[1].channel == CellChannel.STDERR
    assert cell.console[1].data == "stderr message"

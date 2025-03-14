from __future__ import annotations

from typing import Any

import pytest

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import MarimoSyntaxError
from marimo._messaging.ops import serialize
from marimo._plugins.core.json_encoder import WebComponentEncoder
from marimo._utils.parse_dataclass import parse_raw


def as_json(obj: Any):
    return WebComponentEncoder.json_dumps(obj)


timestamp = 0

stderr_output = CellOutput(
    channel=CellChannel.STDERR,
    mimetype="text/plain",
    data="Error!",
    timestamp=0,
)

stdout_output = CellOutput(
    channel=CellChannel.STDOUT,
    mimetype="text/plain",
    data="Hello!",
    timestamp=0,
)

error_output = CellOutput(
    channel=CellChannel.MARIMO_ERROR,
    mimetype="application/vnd.marimo+error",
    data=[MarimoSyntaxError(msg="Syntax Error!")],
    timestamp=0,
)

data_output = CellOutput(
    channel=CellChannel.OUTPUT,
    mimetype="application/vnd.marimo+mimebundle",
    data={
        "text/plain": "hi",
        "text/markdown": "# hi",
    },
    timestamp=0,
)


def test_serialize_cell_output():
    output = serialize(stderr_output)
    assert output == {
        "channel": "stderr",
        "mimetype": "text/plain",
        "data": "Error!",
        "timestamp": 0,
    }

    output = serialize(stdout_output)
    assert output == {
        "channel": "stdout",
        "mimetype": "text/plain",
        "data": "Hello!",
        "timestamp": 0,
    }

    output = serialize(error_output)
    assert output == {
        "channel": "marimo-error",
        "mimetype": "application/vnd.marimo+error",
        "data": [
            {
                "msg": "Syntax Error!",
                "type": "syntax",
            }
        ],
        "timestamp": 0,
    }

    output = serialize(data_output)
    assert output == {
        "channel": "output",
        "mimetype": "application/vnd.marimo+mimebundle",
        "data": {
            "text/plain": "hi",
            "text/markdown": "# hi",
        },
        "timestamp": 0,
    }


@pytest.mark.parametrize(
    "subject", [stderr_output, stdout_output, error_output, data_output]
)
def test_identity(subject: CellOutput):
    serialized = serialize(subject)
    assert subject == parse_raw(serialized, CellOutput)


def test_cell_output_static_methods():
    # Test empty output
    empty = CellOutput.empty()
    assert empty.channel == CellChannel.OUTPUT
    assert empty.mimetype == "text/plain"
    assert empty.data == ""

    # Test stdout method
    stdout = CellOutput.stdout("Hello world")
    assert stdout.channel == CellChannel.STDOUT
    assert stdout.mimetype == "text/plain"
    assert stdout.data == "Hello world"

    # Test stderr method
    stderr = CellOutput.stderr("Error message")
    assert stderr.channel == CellChannel.STDERR
    assert stderr.mimetype == "text/plain"
    assert stderr.data == "Error message"

    # Test stdin method
    stdin = CellOutput.stdin("User input")
    assert stdin.channel == CellChannel.STDIN
    assert stdin.mimetype == "text/plain"
    assert stdin.data == "User input"

    # Test errors method
    errors = CellOutput.errors([MarimoSyntaxError(msg="Test error")])
    assert errors.channel == CellChannel.MARIMO_ERROR
    assert errors.mimetype == "application/vnd.marimo+error"
    assert isinstance(errors.data, list)
    assert len(errors.data) == 1
    assert errors.data[0].msg == "Test error"


def test_cell_output_repr():
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="text/plain",
        data="test data",
        timestamp=123.456,
    )
    repr_str = repr(output)
    assert "CellOutput" in repr_str
    assert "channel=CellChannel.OUTPUT" in repr_str
    assert "mimetype=text/plain" in repr_str
    assert "timestamp=123.456" in repr_str


def test_cell_output_asdict():
    output = CellOutput(
        channel=CellChannel.OUTPUT,
        mimetype="text/plain",
        data="test data",
        timestamp=123.456,
    )
    result = output.asdict()
    assert result["channel"] == "output"
    assert result["mimetype"] == "text/plain"
    assert result["data"] == "test data"
    assert result["timestamp"] == 123.456


def test_cell_channel_repr():
    assert repr(CellChannel.STDOUT) == "stdout"
    assert repr(CellChannel.STDERR) == "stderr"
    assert repr(CellChannel.OUTPUT) == "output"
    assert repr(CellChannel.MARIMO_ERROR) == "marimo-error"

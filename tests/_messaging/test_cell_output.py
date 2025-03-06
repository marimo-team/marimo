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

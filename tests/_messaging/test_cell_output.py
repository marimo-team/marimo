from __future__ import annotations

from marimo._messaging.cell_output import CellChannel, CellOutput


def test_sanitize_plaintext() -> None:
    output = CellOutput(
        channel=CellChannel.STDOUT,
        mimetype="text/plain",
        data="Something <something> something",
    )
    assert output.data == "Something &lt;something&gt; something"


def test_sanitize_html() -> None:
    output = CellOutput(
        channel=CellChannel.STDOUT,
        mimetype="text/html",
        data="Something <something> something",
    )
    assert output.data == "Something <something> something"


def test_sanitize_codehiglight() -> None:
    output = CellOutput(
        channel=CellChannel.STDOUT,
        mimetype="text/plain",
        data='<span class="codehilite">Something <something> something</span>',
    )
    assert (
        output.data
        == '<span class="codehilite">Something <something> something</span>'
    )

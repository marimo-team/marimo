# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from io import TextIOBase

from marimo._cli.print import echo


class CLIExportWriter(TextIOBase):
    def __init__(self, *, err: bool) -> None:
        self._err = err

    def write(self, value: str) -> int:
        echo(value, err=self._err, nl=False)
        return len(value)


STDOUT = CLIExportWriter(err=False)
STDERR = CLIExportWriter(err=True)

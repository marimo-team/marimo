# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.stateless.status._progress import progress_bar
from marimo._runtime.context.utils import running_in_notebook


class ProgressBarTqdmPatch(progress_bar):
    def __init__(self, *args: Any, **kwargs: Any):
        # Partial translation from tqdm to our native progress bar;
        # uses API of tqdm v4.66.4, likely backward compatible.
        iterable: Any = kwargs.get("iterable", None)
        desc: str | None = kwargs.get("desc", None)
        total: int | None = kwargs.get("total", None)

        # In case args were used
        if args:
            iterable = args[0]
        if len(args) >= 2:
            desc = args[1]
        if len(args) >= 3:
            total = args[2]

        super().__init__(
            collection=iterable,
            title=desc or "",
            total=total,
        )

    def update(self, n: int = 1) -> None:
        """Update the progress bar by incrementing it by n.

        Args:
            n (int, optional): Number of iterations to increment by. Defaults to 1.
        """
        if hasattr(self, "progress") and self.progress is not None:
            self.progress.update(increment=n)

    def close(self) -> None:
        """Close the progress bar and clean up.

        This method is called when the progress bar is no longer needed.
        In tqdm, this method also handles styling based on completion status.
        """
        if hasattr(self, "progress") and self.progress is not None:
            self.progress.clear()
            self.progress.close()

    @classmethod
    def write(cls, s: str, file: Any = None, end: str = "\n") -> None:
        """Print a message via tqdm (without overlap with bars).

        Args:
            s (str): The message to print
            file: The file to write to (defaults to sys.stdout)
            end (str): The end character to use (defaults to newline)
        """
        import sys

        fp: Any = file if file is not None else sys.stdout
        # In marimo, we don't need special handling to avoid overlapping with bars
        # as the output is handled differently than in terminal environments
        fp.write(s)
        fp.write(end)


class ProgressBarTrangePatch(ProgressBarTqdmPatch):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(range(*args), **kwargs)


class TqdmFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "tqdm"

    def register(self) -> None:
        if running_in_notebook():
            # Import tqdm.notebook for notebook-specific progress bar implementation
            import tqdm.notebook  # type: ignore [import-not-found,import-untyped] # noqa: E501

            tqdm.notebook.tqdm = ProgressBarTqdmPatch
            tqdm.notebook.trange = ProgressBarTrangePatch

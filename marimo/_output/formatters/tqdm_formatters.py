# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.stateless.status._progress import progress_bar
from marimo._runtime.context.utils import running_in_notebook


class TqdmFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "tqdm"

    def register(self) -> None:
        if running_in_notebook():
            import tqdm.notebook  # type: ignore [import-not-found,import-untyped] # noqa: E501

            def tqdm_to_progress_bar(
                *args: Any, **kwargs: Any
            ) -> progress_bar:
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

                return progress_bar(
                    collection=iterable, title=desc, total=total
                )

            tqdm.notebook.tqdm = tqdm_to_progress_bar

import re
from typing import TYPE_CHECKING, Any

from marimo import mermaid
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import Html

if TYPE_CHECKING:
    import polars as pl

if DependencyManager.polars.has():
    import polars as pl

    @pl.api.register_lazyframe_namespace("mo")
    class Marimo:
        def __init__(self, ldf: pl.LazyFrame):
            self._ldf: pl.LazyFrame = ldf

        def show_graph(self, **kwargs: Any) -> Html | str:
            # We are specifying raw_output already, so we need to remove if it is passed
            raw_output = kwargs.pop("raw_output", False)

            dot = self._ldf.show_graph(raw_output=True, **kwargs)

            if raw_output:
                return dot

            return self._dot_to_mermaid_html(dot)

        # _dot_to_mermaid_html is a separate method from show_graph so that in the future
        # polars can be updated to output mermaid directly when calling native show_graph
        # inside a marimo environment.
        # In order to do that we need a function that will not recursively call show_graph
        @classmethod
        def _dot_to_mermaid_html(self, dot: str) -> Html:
            return mermaid(self._polars_dot_to_mermaid(dot))

        @staticmethod
        def _parse_node_label(label: str) -> str:
            # replace escaped newlines
            label = label.replace(r"\n", "\n")
            # replace escaped quotes
            label = label.replace('\\"', "#quot;")
            return label

        @classmethod
        def _polars_dot_to_mermaid(cls, dot: str) -> str:
            edge_regex = r"(?P<node1>\w+) -- (?P<node2>\w+)"
            node_regex = r"(?P<node>\w+)(\s+)?\[label=\"(?P<label>.*)\"]"

            nodes = [n for n in re.finditer(node_regex, dot)]
            edges = [e for e in re.finditer(edge_regex, dot)]

            return "\n".join(
                [
                    "graph TD",
                    *[
                        f'\t{n["node"]}["{cls._parse_node_label(n["label"])}"]'
                        for n in nodes
                    ],
                    *[f'\t{e["node1"]} --- {e["node2"]}' for e in edges],
                ]
            )

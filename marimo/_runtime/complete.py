# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import html
import queue
from typing import cast

import jedi  # type: ignore # noqa: F401
import jedi.api  # type: ignore # noqa: F401

from marimo import _loggers as loggers
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.ops import CompletionResult
from marimo._messaging.streams import Stream
from marimo._output.md import _md
from marimo._runtime import dataflow
from marimo._runtime.requests import CompletionRequest
from marimo._utils.format_signature import format_signature

LOGGER = loggers.marimo_logger()


def _is_dunder_name(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _should_include_name(name: str, prefix: str) -> bool:
    """Exclude names starting with an underscore, except dunder names."""
    is_dunder_name = _is_dunder_name(name)
    if name.startswith("_"):
        if not is_dunder_name:
            # Never include names that start with a single underscore
            return False
        elif not prefix.startswith("_"):
            return False
        else:
            # Only include dunder names when prefix starts with an underscore
            return True
    else:
        return True


def _get_docstring(completion: jedi.api.classes.BaseName) -> str:
    try:
        body = cast(str, completion.docstring(raw=True))
    except Exception:
        LOGGER.debug("Failed to get docstring for %s", completion.name)
        return ""

    if completion.type == "function":
        prefix = "def "
    elif completion.type == "class":
        prefix = "class "
    else:
        prefix = ""

    try:
        signature_text = "\n\n".join(
            [
                format_signature(prefix, s.to_string())
                for s in completion.get_signatures()
            ]
        )
    except Exception:
        LOGGER.debug("Maybe failed getting signature for %s", completion.name)
        return ""

    if completion.type == "module" and not signature_text:
        signature_text = "module " + completion.name
    elif completion.type == "keyword" and not signature_text:
        signature_text = "keyword " + completion.name

    if signature_text:
        signature_text = _md(
            "```python3\n" + signature_text + "\n```",
            apply_markdown_class=False,
        ).text

    if body:
        body = "<pre>" + html.escape(body) + "</pre>"

    if signature_text and body:
        docstring = signature_text + "\n\n" + body
    else:
        docstring = signature_text + body

    if completion.type == "class":
        # Append the __init__ docstring.
        definitions = completion.goto()
        if (
            definitions
            and len(definitions) == 1
            and isinstance(definitions[0], jedi.api.classes.Name)
        ):
            name = definitions[0]
            for subname in name.defined_names():
                if subname.name.endswith("__init__"):
                    init_docstring = subname.docstring(raw=True)
                    if init_docstring:
                        init_docstring = (
                            "__init__ docstring:\n\n" + init_docstring
                        )
                    if docstring and init_docstring:
                        docstring += "\n\n" + init_docstring
                    else:
                        docstring += init_docstring

    return docstring


def _get_type_hint(completion: jedi.api.classes.BaseName) -> str:
    try:
        type_hint = cast(str, completion.get_type_hint())
    except Exception:
        # sometimes Jedi unexpectedly fails
        return ""

    if type_hint:
        return cast(str, completion.name) + ": " + type_hint
    else:
        return ""


def _get_completion_info(completion: jedi.api.classes.BaseName) -> str:
    if completion.type != "statement":
        return _get_docstring(completion)
    else:
        return _get_type_hint(completion)


def _get_completion_options(
    completion: jedi.api.classes.BaseName, script: jedi.Script
) -> CompletionOption:
    name = completion.name
    kind = completion.type

    # Choose whether the completion info should be from the name
    # or the enclosing function's signature, if any
    symbol_to_lookup = completion
    if completion.type == "param":
        # Show the function/class docstring if available
        signatures = script.get_signatures()
        if len(signatures) == 1:
            symbol_to_lookup = signatures[0]
    completion_info = _get_completion_info(symbol_to_lookup)

    return CompletionOption(
        name=name, type=kind, completion_info=completion_info
    )


def _write_completion_result(
    stream: Stream,
    completion_id: str,
    prefix_length: int,
    options: list[CompletionOption],
) -> None:
    CompletionResult(
        completion_id=completion_id,
        prefix_length=prefix_length,
        options=options,
    ).broadcast(stream=stream)


def _write_no_completions(stream: Stream, completion_id: str) -> None:
    _write_completion_result(stream, completion_id, 0, [])


def complete(
    queue: queue.Queue[CompletionRequest],
    graph: dataflow.DirectedGraph,
    stream: Stream,
) -> None:
    """Code completion worker"""

    while True:
        request = queue.get()
        if not request.document.strip():
            _write_no_completions(stream, request.completion_id)
            continue

        with graph.lock:
            codes = [
                graph.cells[cid].code
                for cid in dataflow.topological_sort(
                    graph,
                    set(graph.cells.keys()) - set([request.cell_id]),
                )
            ]

        try:
            script = jedi.Script("\n".join(codes + [request.document]))
            completions = script.complete()
            prefix_length = (
                completions[0].get_completion_prefix_length()
                if completions
                else 0
            )

            # Only complete an empty symbol (prefix length == 0) when we're
            # using dot notation; this prevents autocomplete from kicking in at
            # awkward times, such as when parentheses are first opened
            if (
                prefix_length == 0
                and len(request.document) >= 1
                and request.document[-1] != "."
            ):
                completions = []

            # If there are still no completions, then bail.
            if not completions:
                _write_no_completions(stream, request.completion_id)
                continue

            prefix = request.document[-prefix_length:]
            options = [
                _get_completion_options(c, script)
                for c in completions
                if _should_include_name(c.name, prefix)
            ]
            _write_completion_result(
                stream=stream,
                completion_id=request.completion_id,
                prefix_length=prefix_length,
                options=options,
            )
        except Exception as e:
            # jedi failed to provide completion
            LOGGER.debug("Completion with jedi failed: ", str(e))
            _write_no_completions(stream, request.completion_id)

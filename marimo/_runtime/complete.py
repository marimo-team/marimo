# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import html
import threading
import time
from typing import TYPE_CHECKING, Any, cast

import jedi  # type: ignore # noqa: F401
import jedi.api  # type: ignore # noqa: F401

from marimo import _loggers as loggers
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.ops import CompletionResult
from marimo._messaging.types import Stream
from marimo._output.md import _md
from marimo._runtime import dataflow
from marimo._runtime.requests import CodeCompletionRequest
from marimo._server.types import QueueType
from marimo._utils.format_signature import format_signature
from marimo._utils.rst_to_html import convert_rst_to_html

if TYPE_CHECKING:
    import threading

LOGGER = loggers.marimo_logger()


# Don't execute properties or __get_item__: when falling back to the Jedi
# interpreter, this leads to an incorrect type hint of properties as modules,
# but at least it prevents execution of side-effecting code.
jedi.settings.allow_unsafe_interpreter_executions = False


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
        # for marimo docstrings, treat them as markdown
        # for other modules, treat them as plain text
        if completion.module_name.startswith("marimo"):
            body = _md(body, apply_markdown_class=False).text
        else:
            try:
                body = (
                    "<div class='external-docs'>"
                    + convert_rst_to_html(body)
                    + "</div>"
                )
            except Exception as e:
                # if docutils chokes, we don't want to crash the completion
                # worker
                LOGGER.debug("Converting RST to HTML failed: ", e)
                body = (
                    "<pre class='external-docs'>"
                    + html.escape(body)
                    + "</pre>"
                )

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
                            "__init__ docstring:\n\n"
                            + _md(
                                init_docstring, apply_markdown_class=False
                            ).text
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
        try:
            return _get_docstring(completion)
        except Exception as e:
            LOGGER.debug("jedi failed to get docstring: %s", str(e))
            return ""
    else:
        try:
            return _get_type_hint(completion)
        except Exception as e:
            LOGGER.debug("jedi failed to get type hint: %s", str(e))
            return ""


def _get_completion_option(
    completion: jedi.api.classes.Completion,
    script: jedi.Script,
    compute_completion_info: bool,
) -> CompletionOption:
    name = completion.name
    kind = completion.type

    if compute_completion_info:
        # Choose whether the completion info should be from the name
        # or the enclosing function's signature, if any
        symbol_to_lookup = completion
        if completion.type == "param":
            # Show the function/class docstring if available
            signatures = script.get_signatures()
            if len(signatures) == 1:
                symbol_to_lookup = signatures[0]
        completion_info = _get_completion_info(symbol_to_lookup)
    else:
        completion_info = ""

    return CompletionOption(
        name=name, type=kind, completion_info=completion_info
    )


def _get_completion_options(
    completions: list[jedi.api.classes.Completion],
    script: jedi.Script,
    prefix: str,
    limit: int,
    timeout: float,
) -> list[CompletionOption]:
    if len(completions) > limit:
        return [
            _get_completion_option(
                completion, script, compute_completion_info=False
            )
            for completion in completions
            if _should_include_name(completion.name, prefix)
        ]

    completion_options: list[CompletionOption] = []
    start_time = time.time()
    for completion in completions:
        if not _should_include_name(completion.name, prefix):
            continue
        elapsed_time = time.time() - start_time
        completion_options.append(
            _get_completion_option(
                completion,
                script,
                compute_completion_info=elapsed_time < timeout,
            )
        )
    return completion_options


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


def _drain_queue(
    completion_queue: QueueType[CodeCompletionRequest],
) -> CodeCompletionRequest:
    """Drain the queue of completion requests, returning the most recent one"""

    request = completion_queue.get()
    while not completion_queue.empty():
        request = completion_queue.get()
    return request


def _get_completions_with_script(
    codes: list[str], document: str
) -> tuple[jedi.Script, list[jedi.api.classes.Completion]]:
    script = jedi.Script("\n".join(codes + [document]))
    completions = script.complete()
    return script, completions


def _get_completions_with_interpreter(
    document: str, glbls: dict[str, Any], glbls_lock: threading.RLock
) -> tuple[jedi.Script, list[jedi.api.classes.Completion]]:
    # Jedi fails to statically analyze some libraries, like ibis,
    # so we fall back to interpreter-based completions.
    #
    # Interpreter-based completions execute code, so we need to grab a
    # lock on the globals dict. This is best-effort -- if the kernel
    # has locked globals, we simply don't complete instead of waiting
    # for the lock to be released.
    script = jedi.Interpreter(document, [glbls])
    locked = False
    completions = []
    locked = glbls_lock.acquire(blocking=False)
    if locked:
        LOGGER.debug("Completion worker acquired globals lock")
        completions = script.complete()
    return script, completions


def _get_completions(
    codes: list[str],
    document: str,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
    prefer_interpreter_completion: bool,
) -> tuple[jedi.Script, list[jedi.api.classes.Completion]]:
    if prefer_interpreter_completion:
        script, completions = _get_completions_with_interpreter(
            document, glbls, glbls_lock
        )
        if not completions:
            script, completions = _get_completions_with_script(codes, document)
        return script, completions
    else:
        script, completions = _get_completions_with_script(codes, document)
        if not completions:
            script, completions = _get_completions_with_interpreter(
                document, glbls, glbls_lock
            )
        return script, completions


def complete(
    request: CodeCompletionRequest,
    graph: dataflow.DirectedGraph,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
    stream: Stream,
    docstrings_limit: int = 80,
    timeout: float | None = None,
    prefer_interpreter_completion: bool = False,
) -> None:
    """Gets code completions for a request.

    If `prefer_interpreter_completion`, a runtime-based method is used,
    falling back to a static analysis method. Otherwise the static method
    is used, with the interpreter method as a fallback.

    Static completions are safer since they don't execute code, but they
    are slower and sometimes fail. Interpreter executions are faster
    and more comprehensive, but can only be carried out when the kernel
    isn't executing or otherwise handling a request.

    **Args.**

    - `request`: the completion request
    - `graph`: dataflow graph backing the marimo program
    - `glbls`: global namespace
    - `glbls_lock`: lock protecting the global namespace, for interpreter-based
         completion
    - `stream`: Stream through which to communicate completion results
    - `docstrings_limit`: limit past which we won't attempt to fetch type hints
          and docstrings
    - `timeout`: timeout after which we'll stop fetching type hints/docstrings
    - `prefer_interpreter_completion`: whether to prefer interpreter completion
    """
    if not request.document.strip():
        _write_no_completions(stream, request.id)
        return

    with graph.lock:
        codes = [
            graph.cells[cid].code
            for cid in dataflow.topological_sort(
                graph,
                set(graph.cells.keys()) - set([request.cell_id]),
            )
        ]

    try:
        script, completions = _get_completions(
            codes,
            request.document,
            glbls,
            glbls_lock,
            prefer_interpreter_completion,
        )
        prefix_length = (
            completions[0].get_completion_prefix_length() if completions else 0
        )

        # Only complete an empty symbol (prefix length == 0) when we're
        # using dot notation; this prevents autocomplete from kicking in at
        # awkward times, such as when parentheses are first opened
        if (
            prefix_length == 0
            and len(request.document) >= 1
            and request.document[-1] != "."
        ):
            # Empty prefix, not dot notation; don't complete ...
            completions = []

            # Get docstring in function context. A bit of a hack, since
            # this isn't actually a completion, just a tooltip.
            #
            # If no completions, we might be getting a signature ...
            # for example, if the document is "mo.ui.slider(start=1,
            signatures = script.get_signatures()
            if signatures:
                _write_completion_result(
                    stream=stream,
                    completion_id=request.id,
                    prefix_length=0,
                    options=[
                        CompletionOption(
                            name=signatures[0].name,
                            type="tooltip",
                            completion_info=_get_completion_info(
                                signatures[0]
                            ),
                        )
                    ],
                )
                return

        if not completions:
            # If there are still no completions, then bail.
            _write_no_completions(stream, request.id)
            return

        prefix = request.document[-prefix_length:]
        if timeout is None and isinstance(script, jedi.Interpreter):
            # We're holding the globals lock; set a short timeout so we don't
            # block the kernel
            timeout = 1
        elif timeout is None:
            # We're not blocking the kernel so we can afford to take longer
            timeout = 2

        options = _get_completion_options(
            completions,
            script,
            prefix=prefix,
            limit=docstrings_limit,
            timeout=timeout,
        )
        _write_completion_result(
            stream=stream,
            completion_id=request.id,
            prefix_length=prefix_length,
            options=options,
        )
    except Exception as e:
        # jedi failed to provide completion
        LOGGER.debug("Completion with jedi failed: ", str(e))
        _write_no_completions(stream, request.id)
    finally:
        try:
            # if an interpreter was used, the lock might be held
            glbls_lock.release()
        except Exception:
            # RLock raises if released when not acquired.
            pass
        else:
            LOGGER.debug("Completion worker released globals lock.")


def completion_worker(
    completion_queue: QueueType[CodeCompletionRequest],
    graph: dataflow.DirectedGraph,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
    stream: Stream,
) -> None:
    """Code completion worker.


    **Args:**

    - `completion_queue`: queue from which requests are pulled.
    - `graph`: dataflow graph backing the marimo program
    - `glbls`: dictionary of global variables in interpreter memory
    - `glbls_lock`: lock protecting globals
    - `stream`: stream used to communicate completion results
    """

    while True:
        request = _drain_queue(completion_queue)
        complete(
            request=request,
            graph=graph,
            glbls=glbls,
            glbls_lock=glbls_lock,
            stream=stream,
        )

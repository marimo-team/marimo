# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import html
import sys
import threading
import time
from collections.abc import Collection, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, cast

import jedi  # type: ignore # noqa: F401
import jedi.api  # type: ignore # noqa: F401

from marimo import _loggers as loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.ops import CompletionResult
from marimo._messaging.types import Stream
from marimo._output.md import _md
from marimo._runtime import dataflow
from marimo._runtime.requests import CodeCompletionRequest
from marimo._server.types import QueueType
from marimo._utils.docs import MarimoConverter
from marimo._utils.format_signature import format_signature
from marimo._utils.rst_to_html import convert_rst_to_html

if TYPE_CHECKING:
    import threading
    from types import ModuleType

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


DOC_CACHE_SIZE = 200
# Normally '.' is the trigger character for completions.
#
# We also want to trigger completions on '(', ',' because
# we don't open the signature popup on these characters.
#
# We also add '/' for file path completion.
COMPLETION_TRIGGER_CHARACTERS = frozenset({".", "(", ",", "/"})


@lru_cache(maxsize=DOC_CACHE_SIZE)
def _build_docstring_cached(
    completion_type: str,
    completion_name: str,
    signature_strings: tuple[str, ...],
    raw_body: str | None,
    init_docstring: str | None,
) -> str:
    """Builds the docstring that includes signatures and body."""
    if not signature_strings:
        # handle modules, keywords, etc.
        if completion_type == "module":
            signature_text = "module " + completion_name
        elif completion_type == "keyword":
            signature_text = "keyword " + completion_name
        else:
            signature_text = ""
    else:
        merged_sig = "\n\n".join(
            [
                format_signature(
                    (
                        "def "
                        if completion_type == "function"
                        else "class "
                        if completion_type == "class"
                        else ""
                    ),
                    s,
                )
                for s in signature_strings
            ]
        )
        signature_text = _md(
            f"```python3\n{merged_sig}\n```",
            apply_markdown_class=False,
        ).text

    body_converted = (
        _convert_docstring_to_markdown(raw_body) if raw_body else ""
    )

    if signature_text and body_converted:
        docstring = signature_text + "\n\n" + body_converted
    else:
        docstring = signature_text + body_converted

    if init_docstring:
        docstring += "\n\n" + init_docstring

    return docstring


doc_convert = MarimoConverter()


def _convert_docstring_to_markdown(raw_docstring: str) -> str:
    """
    Convert raw docstring to markdown then to HTML.
    """

    def as_md_html(raw: str) -> str:
        return _md(raw, apply_markdown_class=False).text

    # Prefer using docstring_to_markdown if available
    # which uses our custom MarimoConverter
    if DependencyManager.docstring_to_markdown.has():
        import docstring_to_markdown  # type: ignore

        return as_md_html(docstring_to_markdown.convert(raw_docstring))

    # Then try our custom MarimoConverter
    if doc_convert.can_convert(raw_docstring):
        return as_md_html(doc_convert.convert(raw_docstring))

    # Then try RST
    try:
        return (
            "<div class='external-docs'>"
            + convert_rst_to_html(raw_docstring)
            + "</div>"
        )
    except Exception:
        # Then return plain text
        # if docutils chokes, we don't want to crash the completion
        # worker
        return (
            "<pre class='external-docs'>"
            + html.escape(raw_docstring)
            + "</pre>"
        )


def _get_docstring(completion: jedi.api.classes.BaseName) -> str:
    try:
        raw_body = cast(str, completion.docstring(raw=True))
    except Exception:
        LOGGER.debug("Failed to get docstring for %s", completion.name)
        return ""

    # Glean raw signatures
    try:
        signature_strings = tuple(
            s.to_string() for s in completion.get_signatures()
        )
    except Exception:
        LOGGER.debug("Maybe failed getting signature for %s", completion.name)
        return ""

    init_docstring = ""
    if completion.type == "class":
        # Possibly append the __init__ docstring, if it exists
        definitions: list[jedi.api.classes.Name] = completion.goto()
        if (
            definitions
            and len(definitions) == 1
            and isinstance(definitions[0], jedi.api.classes.Name)
        ):
            for subname in definitions[0].defined_names():
                if subname.name.endswith("__init__"):
                    raw_init = subname.docstring(raw=True)
                    if raw_init:
                        init_docstring = (
                            "__init__ docstring:\n\n"
                            + _md(raw_init, apply_markdown_class=False).text
                        )

    # Build final docstring
    return _build_docstring_cached(
        completion.type,
        completion.name,
        signature_strings,
        raw_body,
        init_docstring or None,
    )


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
    completions: list[jedi.api.classes.Completion] = []
    locked = glbls_lock.acquire(blocking=False)
    if locked:
        LOGGER.debug("Completion worker acquired globals lock")
        completions = script.complete()
    return script, completions


# TODO move this to a global utility module
def _isinstance_external(obj: Any, *, class_ref: str) -> bool:
    """Check if an object is an instance of a class reference defined by a string.
    Allows to define and do `isinstance()` checks without importing 3rd party libraries

    Example:
        ```python
        df = pd.DataFrame(...)
        _isinstance_external(df, class_ref="pandas.DataFrame")
        ```
    """
    import_parts = class_ref.split(".")
    module_name = import_parts[0]

    if module_name not in sys.modules:
        return False

    module: ModuleType = sys.modules[module_name]
    target_class: Any = module
    for part in import_parts:
        target_class = getattr(target_class, part)

    return isinstance(obj, target_class)


class HasKeysMethod(Protocol):
    def keys(self) -> Collection[Any]: ...


class HasColumnsProperty(Protocol):
    @property
    def columns(self) -> Collection[Any]: ...


def _key_options_from_ipython_method(obj: Any) -> list[str]:
    # convention for `_ipython_key_completions_` is to return a list of strings
    return [str(key) for key in obj._ipython_key_completions_()]


def _key_options_via_keys_method(obj: HasKeysMethod) -> list[str]:
    return [str(key) for key in obj.keys()]


# TODO refactor to customize the `CompletionOption.info` with `"columns"`
def _key_options_via_columns_method(obj: HasColumnsProperty) -> list[str]:
    return [str(col) for col in obj.columns]


def _key_options_dispatcher(obj: Any) -> list[str]:
    """Tries to get key completion suggestions from `obj`
    based on its methods and type.

    Returns a list of strings to later create marimo `CompletionOption`
    """
    if getattr(obj, "_ipython_key_completions_", False):
        return _key_options_from_ipython_method(obj)
    elif isinstance(obj, Mapping):
        return _key_options_via_keys_method(obj)
    elif _isinstance_external(obj, class_ref="pandas.DataFrame"):
        return _key_options_via_columns_method(obj)
    elif _isinstance_external(obj, class_ref="polars.DataFrame"):
        return _key_options_via_columns_method(obj)

    LOGGER.debug(
        f"No matching handlers found to retrieve keys from type `{type(obj)}`"
    )
    return []


def _get_key_options(
    script: jedi.Script, glbls: dict[str, Any]
) -> list[CompletionOption]:
    """Get completion values for trigger `["` or `['`. Values are meant to be
    passed to `.__getitem__()`

    This implementation assumes that marimo's `CompletionRequest.document`
    only includes current line, up to the completion trigger.
    """
    names = script.get_names(
        references=True, definitions=False, all_scopes=False
    )
    if not names:
        LOGGER.debug(
            f"Retrieved no `names` for completion request: `{script._code}`"
        )
        return []

    obj_name = names[-1].name
    obj = glbls.get(obj_name)
    if obj is None:
        LOGGER.debug(f"Failed to find `{obj_name=:}` in `glbls`")
        return []

    keys = _key_options_dispatcher(obj)
    # TODO currently unreliable for non-string keys, even if stringified
    # seems to be related to serialization issue if include `"(True, False)` (no closing quote)
    return [
        CompletionOption(name=key, type="property", completion_info="key")
        for key in keys
    ]


def _maybe_get_key_options(
    request: CodeCompletionRequest,
    script: jedi.Script,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
) -> list[CompletionOption]:
    """Call key completions methods if the request contains the trigger"""
    triggers = ('["', "['")  # explicitly handle both quotation characters
    if request.document[-2:] not in triggers:
        return []

    # TODO ideally, we don't acquire the lock twice with `_get_completions_with_interpreter()` and `_maybe_get_key_options`
    # however, the two functions are applied on different triggers
    # also, this other function returns Jedi `Completion` while this returns native `CompletionOption`
    locked = False
    locked = glbls_lock.acquire(blocking=False)
    if locked:
        try:
            return _get_key_options(script, glbls)
        finally:
            glbls_lock.release()
    else:
        return []


def _get_completions(
    codes: list[str],
    document: str,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
) -> tuple[jedi.Script, list[jedi.api.classes.Completion]]:
    script, completions = _get_completions_with_script(codes, document)
    completions = script.complete()
    if not completions:
        script, completions = _get_completions_with_interpreter(
            document, glbls, glbls_lock
        )
    return script, completions


# NOTE you will hit front display bug if the result set doesn't
# share the same `prefix_length`. This could happen if completion values
# are generated via different means
def complete(
    request: CodeCompletionRequest,
    graph: dataflow.DirectedGraph,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
    stream: Stream,
    docstrings_limit: int = 80,
    timeout: float | None = None,
) -> None:
    """Gets code completions for a request.

    Static completions are safer since they don't execute code, but they
    are slower and sometimes fail. Interpreter executions are faster
    and more comprehensive, but can only be carried out when the kernel
    isn't executing or otherwise handling a request.

    Args:
        request: The completion request
        graph: Dataflow graph backing the marimo program
        glbls: Global namespace
        glbls_lock: Lock protecting the global namespace, for interpreter-based
            completion
        stream: Stream through which to communicate completion results
        docstrings_limit: Limit past which we won't attempt to fetch type hints
            and docstrings
        timeout: Timeout after which we'll stop fetching type hints/docstrings
        prefer_interpreter_completion: Whether to prefer interpreter completion
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

    completions: list[jedi.api.classes.Completion] = []
    try:
        script, completions = _get_completions(
            codes,
            request.document,
            glbls,
            glbls_lock,
        )
        prefix_length: int = (
            completions[0].get_completion_prefix_length() if completions else 0
        )
        prefix = request.document[-prefix_length:]

        key_options = _maybe_get_key_options(
            request,
            script,
            glbls=glbls,
            glbls_lock=glbls_lock,
        )
        # if `key_options` are found, return early
        # we can return because key and attribute completions have non-overlapping triggers
        if key_options:
            _write_completion_result(
                stream=stream,
                completion_id=request.id,
                prefix_length=0,  # values is static because of our implementation
                options=key_options,
            )
            return

        if (
            prefix_length == 0
            and len(request.document) >= 1
            and request.document[-1] not in COMPLETION_TRIGGER_CHARACTERS
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


    Args:
        completion_queue: queue from which requests are pulled.
        graph: dataflow graph backing the marimo program
        glbls: dictionary of global variables in interpreter memory
        glbls_lock: lock protecting globals
        stream: stream used to communicate completion results
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

# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import html
import re
import sys
import time
from collections.abc import Collection, Mapping
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Protocol, cast

import jedi  # type: ignore
import jedi.api  # type: ignore

from marimo import _loggers as loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.completion_option import CompletionOption
from marimo._messaging.notification import CompletionResultNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._messaging.types import Stream
from marimo._output.md import _md
from marimo._runtime import dataflow
from marimo._runtime.commands import CodeCompletionCommand
from marimo._types.ids import RequestId
from marimo._utils.docs import MarimoConverter, google_docstring_to_markdown
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
        # Only include dunder names when prefix starts with an underscore
        return True
    else:
        return True


DOC_CACHE_SIZE = 200
# Characters that trigger the completion list when the prefix is empty.
#
# `.` triggers attribute completions and `/` triggers file-path completions.
#
# We intentionally do NOT trigger the completion list on `(` or `,`. At those
# positions Jedi has no prefix to filter on and returns the entire namespace
# (every builtin and global), producing a noisy popup and accidental
# completions (e.g. after typing `1,`). Instead, an empty prefix after these
# characters falls through to signature help below, which is the useful
# behavior inside a call's argument list (e.g. `mo.ui.slider(start=1,`).
COMPLETION_TRIGGER_CHARACTERS = frozenset({".", "/"})
# Matches an import statement whose cursor sits at a name position with an empty
# prefix, e.g. `from dataclasses import ` or `import ` or `from a import b, `.
# Unlike an empty prefix after `(`/`,` (which yields the entire namespace), Jedi
# returns only the relevant, bounded set of importable names here, so completing
# on an empty prefix is the useful behavior. Operates on the final line only.
_IMPORT_COMPLETION_PATTERN = re.compile(
    r"\s*(?:from\s+[\w.]+\s+)?import\s+(?:\w+(?:\s+as\s+\w+)?\s*,\s*)*$"
)


def _is_import_completion_context(document: str) -> bool:
    """Return True when the cursor is at an import-name position (empty prefix)."""
    last_line = document.rsplit("\n", 1)[-1]
    return _IMPORT_COMPLETION_PATTERN.match(last_line) is not None


# Matches display bracket delimiters: \[...\]
_MATH_DISPLAY_BRACKET_PATTERN = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
# Matches inline paren delimiters: \(...\)
_MATH_INLINE_PAREN_PATTERN = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
# Matches display dollar delimiters: $$...$$
_MATH_DISPLAY_DOLLAR_PATTERN = re.compile(
    r"(?<!\\)\$\$(.+?)(?<!\\)\$\$",
    re.DOTALL,
)
# Matches inline dollar delimiters: $...$
_MATH_INLINE_DOLLAR_PATTERN = re.compile(
    r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)"
)


def _contains_math_syntax(text: str) -> bool:
    """Return True when a docstring contains supported math delimiters."""
    return (
        ".. math::" in text
        or ":math:`" in text
        or ":math:<code>" in text
        or _MATH_DISPLAY_BRACKET_PATTERN.search(text) is not None
        or _MATH_INLINE_PAREN_PATTERN.search(text) is not None
        or _MATH_DISPLAY_DOLLAR_PATTERN.search(text) is not None
        or _MATH_INLINE_DOLLAR_PATTERN.search(text) is not None
    )


@lru_cache(maxsize=DOC_CACHE_SIZE)
def _build_docstring_cached(
    completion_type: str,
    completion_name: str,
    signature_strings: tuple[str, ...],
    raw_body: str | None,
    init_docstring: str | None,
    param_types: tuple[tuple[str, str], ...] = (),
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
        _convert_docstring_to_markdown(raw_body, dict(param_types))
        if raw_body
        else ""
    )

    if signature_text and body_converted:
        docstring = signature_text + "\n\n" + body_converted
    else:
        docstring = signature_text + body_converted

    if init_docstring:
        docstring += "\n\n" + init_docstring

    return docstring


doc_convert = MarimoConverter()


def _convert_docstring_to_markdown(
    raw_docstring: str, param_types: dict[str, str] | None = None
) -> str:
    """
    Convert raw docstring to markdown then to HTML.
    """

    def as_md_html(raw: str) -> str:
        return _md(raw, apply_markdown_class=False).text

    # Prefer our Google converter when applicable so signature types can
    # fill in missing Args table types.
    if doc_convert.can_convert(raw_docstring):
        return as_md_html(
            google_docstring_to_markdown(
                raw_docstring, param_types=param_types
            )
        )

    # Prefer using docstring_to_markdown if available
    # which uses our custom MarimoConverter
    if DependencyManager.docstring_to_markdown.has():
        import docstring_to_markdown  # type: ignore

        try:
            return as_md_html(docstring_to_markdown.convert(raw_docstring))
        except docstring_to_markdown.UnknownFormatError:
            LOGGER.debug(
                "docstring_to_markdown could not infer docstring format; "
                "falling back",
            )

    # Prefer markdown rendering when math syntax is present.
    # This ensures ``.. math::`` and markdown delimiters are interpreted by
    # the same TeX pipeline used elsewhere in marimo output.
    if _contains_math_syntax(raw_docstring):
        return as_md_html(raw_docstring)

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


def _param_types_from_signatures(
    signatures: list[jedi.api.classes.Signature],
) -> dict[str, str]:
    """Extract parameter type hints from a Jedi signature."""
    if not signatures:
        return {}
    params = getattr(signatures[0], "params", None)
    if not params:
        return {}
    param_types: dict[str, str] = {}
    for param in params:
        try:
            type_hint = cast(str, param.get_type_hint())
        except Exception:
            continue
        if type_hint:
            param_types[param.name] = type_hint
    return param_types


def _get_docstring(completion: jedi.api.classes.BaseName) -> str:
    try:
        raw_body = cast(str, completion.docstring(raw=True))
    except Exception:
        LOGGER.debug("Failed to get docstring for %s", completion.name)
        return ""

    # Glean raw signatures
    try:
        signature_objects = completion.get_signatures()
        signature_strings = tuple(s.to_string() for s in signature_objects)
        param_types = _param_types_from_signatures(signature_objects)
        sorted_param_types = sorted(param_types.items())
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
                            + _convert_docstring_to_markdown(raw_init)
                        )

    # Build final docstring
    return _build_docstring_cached(
        completion.type,
        completion.name,
        signature_strings,
        raw_body,
        init_docstring or None,
        tuple(sorted_param_types),
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


# Jedi types that carry a signature/docstring worth surfacing in live docs.
_DOCUMENTABLE_TYPES = ("function", "class", "module")


def _resolve_aliased_definition(
    completion: jedi.api.classes.BaseName,
) -> jedi.api.classes.BaseName | None:
    """Follow an assignment statement to its underlying definition.

    Aliases such as `func = another_func` are reported by Jedi as a `statement`
    with no docstring of their own, so we infer the assignment to surface the
    docstring and signature of the function/class/module it points at.

    Only an unambiguous, single definition is resolved; multiple candidates
    (e.g. a conditional assignment) would mean guessing which docs to show, so
    we defer to the type hint instead.
    """
    try:
        inferred = completion.infer()
    except Exception:
        return None
    documentable = [d for d in inferred if d.type in _DOCUMENTABLE_TYPES]
    if len(documentable) == 1:
        return documentable[0]
    return None


def _get_completion_info(completion: jedi.api.classes.BaseName) -> str:
    try:
        if completion.type == "statement":
            definition = _resolve_aliased_definition(completion)
            # Fall back to the type hint when the alias has no resolvable
            # definition, or when its docstring comes back empty.
            if definition is not None:
                docstring = _get_docstring(definition)
                if docstring:
                    return docstring
            return _get_type_hint(completion)
        return _get_docstring(completion)
    except Exception as e:
        LOGGER.debug("jedi failed to get completion info: %s", str(e))
        return ""


def _get_completion_option(
    completion: jedi.api.classes.Completion,
    compute_completion_info: bool,
    compute_type: bool = True,
) -> CompletionOption:
    name = completion.name
    # `completion.type` triggers jedi inference and can be surprisingly
    # expensive on cold caches for heavy libraries (pandas, numpy, torch).
    # When callers are already over budget they pass `compute_type=False`, in
    # which case we also skip docstring computation — it re-triggers the same
    # inference we just declined to pay for.
    if not compute_type:
        return CompletionOption(name=name, type="", completion_info="")

    kind = completion.type

    if compute_completion_info:
        # Show the completion's own documentation. For a parameter this is the
        # description of that single parameter, which
        # `patch_jedi_parameter_completion` extracts from the enclosing
        # function's docstring. We deliberately do not fall back to the full
        # function docstring: repeating it for every parameter is noisy, and
        # the signature hint already provides function-level context when the
        # call is opened.
        completion_info = _get_completion_info(completion)
    else:
        completion_info = ""

    return CompletionOption(
        name=name, type=kind, completion_info=completion_info
    )


def _get_completion_options(
    completions: list[jedi.api.classes.Completion],
    prefix: str,
    limit: int,
    timeout: float,
) -> list[CompletionOption]:
    # For large completion sets (e.g. `pd.`, ~140 attrs), building per-item
    # docstrings costs seconds of jedi inference that the user will never read.
    # Skip docstrings globally past `limit` and rely on the time budget to bail
    # out of further type inference if we're already slow.
    compute_docstrings = len(completions) <= limit

    completion_options: list[CompletionOption] = []
    deadline = time.monotonic() + timeout
    for completion in completions:
        if not _should_include_name(completion.name, prefix):
            continue
        under_time_budget = time.monotonic() < deadline
        completion_options.append(
            _get_completion_option(
                completion,
                compute_completion_info=compute_docstrings
                and under_time_budget,
                compute_type=under_time_budget,
            )
        )
    return completion_options


def _write_completion_result(
    stream: Stream,
    completion_id: RequestId,
    prefix_length: int,
    options: list[CompletionOption],
) -> None:
    broadcast_notification(
        CompletionResultNotification(
            completion_id=completion_id,
            prefix_length=prefix_length,
            options=options,
        ),
        stream,
    )


def _write_no_completions(stream: Stream, completion_id: RequestId) -> None:
    _write_completion_result(stream, completion_id, 0, [])


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


class HasColumnsProperty(Protocol):
    @property
    def columns(self) -> Collection[Any]: ...


def _key_options_from_ipython_method(obj: Any) -> list[str]:
    # convention for `_ipython_key_completions_` is to return a list of strings
    return [str(key) for key in obj._ipython_key_completions_()]


def _key_options_via_keys_method(obj: Mapping[Any, Any]) -> list[str]:
    """Completion keys from a mapping. Only used after `isinstance(obj, Mapping)`."""
    return [str(key) for key in obj]


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
    elif _isinstance_external(
        obj, class_ref="pandas.DataFrame"
    ) or _isinstance_external(obj, class_ref="polars.DataFrame"):
        return _key_options_via_columns_method(obj)

    LOGGER.debug(
        f"No matching handlers found to retrieve keys from type `{type(obj)}`"
    )
    return []


# NOTE need to be careful because `__getitem__` can trigger arbitrary code
def _resolve_chained_key_path(obj_name: str, document: str) -> list[list[str]]:
    """Resolve the object chained key access from source code

    Example:
        ```python
        key_path = _resolve_chained_key_path("obj", 'obj["foo"]["bar"]["')
        key_path == [["foo"], ["bar"]]
        ```
    """
    import parso  # jedi dependency
    from parso.utils import split_lines

    # because marimo `CompletionRequest` sends source code up to the cursor position
    # we know only the last line matters for autcompletion.
    line_containing_trigger = split_lines(document)[-1]
    ast_ = parso.parse(line_containing_trigger)  # type: ignore[no-untyped-call]
    # we expect to always hit an error node because `dictionary["` is invalid Python syntax
    root_node = next(
        node for node in ast_.children if node.type == "error_node"
    )

    key_path = []
    seen_object_node = False
    # TODO robust handling of different node types
    for node in root_node.children:
        if obj_name in node.get_code():
            seen_object_node = True
            continue

        # iterate until we find the node associated with `obj_name`
        if seen_object_node is False:
            continue

        # if nodes directly after `obj_name` node are not key accessor `[""]`, exit
        # we expect to never hit this condition
        if node.type != "trailer":
            break

        key_path.append(ast.literal_eval(node.get_code()))

    return key_path


def _get_key_options(
    script: jedi.Script,
    glbls: dict[str, Any],
    document: str,
) -> list[CompletionOption]:
    """Get completion values for trigger `["` or `['`. Values are meant to be
    passed to `.__getitem__()`
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
    root_obj = glbls.get(obj_name)
    if root_obj is None:
        LOGGER.debug(f"Failed to find `{obj_name=}` in `glbls`")
        return []

    obj = root_obj
    for key in _resolve_chained_key_path(obj_name, document):
        try:
            obj = obj.__getitem__(*key)
        except Exception:
            LOGGER.debug(
                f"Failed to retrieve keys `{key}` based on `{document=}`"
            )
            # exit early if `__getitem__` fails and return no completion
            # e.g., no completion is possible if key `"foo"` is invalid in `dictionary["foo"]["`
            return []

    key_options = _key_options_dispatcher(obj)
    # TODO currently unreliable for non-string keys, even if stringified
    # seems to be related to serialization issue if include `"(True, False)` (no closing quote)
    return [
        CompletionOption(
            name=key_option, type="property", completion_info="key"
        )
        for key_option in key_options
    ]


def _maybe_get_key_options(
    document: str,
    script: jedi.Script,
    glbls: dict[str, Any],
    glbls_lock: threading.RLock,
) -> list[CompletionOption]:
    """Call key completions methods if the request contains the trigger"""
    triggers = ('["', "['")  # explicitly handle both quotation characters
    if document[-2:] not in triggers:
        return []

    # TODO ideally, we don't acquire the lock twice with `_get_completions_with_interpreter()` and `_maybe_get_key_options`
    # however, the two functions are applied on different triggers
    # also, this other function returns Jedi `Completion` while this returns native `CompletionOption`
    locked = False
    locked = glbls_lock.acquire(blocking=False)
    if locked:
        try:
            return _get_key_options(script, glbls, document)
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
    try:
        script, completions = _get_completions_with_script(codes, document)
        if completions:
            return script, completions
    except Exception as e:
        # jedi's static analysis can crash while inferring some code — for
        # example https://github.com/davidhalter/jedi/issues/1990).
        # Fallback to interpreter when it crashes
        LOGGER.debug("Completion with jedi Script failed: %s", str(e))
    return _get_completions_with_interpreter(document, glbls, glbls_lock)


# NOTE you will hit front display bug if the result set doesn't
# share the same `prefix_length`. This could happen if completion values
# are generated via different means
def complete(
    request: CodeCompletionCommand,
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
                set(graph.cells.keys()) - {request.cell_id},
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
        # `document[-0:]` is the whole document, not an empty string, so guard
        # the empty-prefix case explicitly.
        prefix = request.document[-prefix_length:] if prefix_length else ""

        key_options = _maybe_get_key_options(
            request.document,
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

        # `/` triggers file-path completion inside strings. As an arithmetic
        # operator (e.g. `1 / `) it sits at an expression position where Jedi
        # returns the entire namespace, so only honor it as a trigger when the
        # results are actually paths. Jedi tags path completions with
        # `type == "path"`, and a path context yields only path completions, so
        # checking the first is enough (and avoids inferring the whole list).
        last_char = request.document[-1:]
        is_trigger_char = last_char in COMPLETION_TRIGGER_CHARACTERS
        if is_trigger_char and last_char == "/":
            is_trigger_char = (
                bool(completions) and completions[0].type == "path"
            )

        in_import_context = _is_import_completion_context(request.document)
        if (
            prefix_length == 0
            and request.document
            and not is_trigger_char
            and not in_import_context
        ):
            # Empty prefix, not dot notation or an import statement;
            # don't complete ...
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

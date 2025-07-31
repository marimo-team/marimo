# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import functools
import sys
import textwrap
import types
from typing import TYPE_CHECKING, Any, Callable

from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import marimo_browser, marimo_pdb
from marimo._utils.platform import is_pyodide

Unpatch = Callable[[], None]

if TYPE_CHECKING:
    from collections.abc import Iterator

    from jedi.inference.base_value import (  # type: ignore[import-untyped]
        ValueSet,
    )
    from parso.python.tree import ExprStmt


def patch_pdb(debugger: marimo_pdb.MarimoPdb) -> None:
    import pdb

    # Patch Pdb so manually instantiated debuggers create our debugger
    pdb.Pdb = marimo_pdb.MarimoPdb  # type: ignore[misc, assignment]
    pdb.set_trace = functools.partial(marimo_pdb.set_trace, debugger=debugger)

    # Used on failure for step through
    pdb.post_mortem = debugger.post_mortem


def patch_webbrowser() -> None:
    import webbrowser

    try:
        _ = webbrowser.get()
    # pyodide doesn't have a webbrowser.get() method
    # (nor a webbrowser.Error, so careful)
    except AttributeError:
        webbrowser.open = marimo_browser.browser_open_fallback
    except webbrowser.Error:
        MarimoBrowser = marimo_browser.build_browser_fallback()
        webbrowser.register(
            "marimo-output",
            None,
            MarimoBrowser(),
            preferred=True,
        )


def patch_sys_module(module: types.ModuleType) -> None:
    sys.modules[module.__name__] = module


def patch_pyodide_networking() -> None:
    import pyodide_http  # type: ignore

    pyodide_http.patch_all()


def patch_recursion_limit(limit: int) -> None:
    """Set the recursion limit."""

    # jedi increases the recursion limit as a side effect, upon import ...
    import jedi  # type: ignore # noqa: F401

    sys.setrecursionlimit(limit)


def patch_micropip(glbls: dict[Any, Any]) -> None:
    """Mock micropip with no-ops"""

    definitions = textwrap.dedent(
        """\
from importlib.abc import Loader, MetaPathFinder
from importlib.util import spec_from_loader

class _MicropipFinder(MetaPathFinder):

    def find_spec(self, fullname, path, target=None):
        if fullname == 'micropip':
            return spec_from_loader(fullname, _MicropipLoader())
        return None


class _MicropipLoader(Loader):
    def create_module(self, spec):
        del spec
        # use default spec creation
        return None

    def exec_module(self, module):
        import textwrap

        code = textwrap.dedent(
'''\
def _warn_uninstalled(prefix=""):
    import sys
    sys.stderr.write(prefix + 'micropip is only available in WASM notebooks.')

async def install(
    requirements, keep_going=False, deps=True,
    credentials=None, pre=False, index_urls=None, *,
    verbose=False
):
    _warn_uninstalled(prefix=f'{requirements} was not installed: ')

def list():
    _warn_uninstalled()

def freeze():
    _warn_uninstalled()

def add_mock_package(name, version, *, modules=None, persistent=False):
    _warn_uninstalled()

def list_mock_packages():
    _warn_uninstalled()

def remove_mock_package(name):
    _warn_uninstalled()

def uninstall(packages, *, verbose=False):
    _warn_uninstalled()

def set_index_urls(urls):
    _warn_uninstalled()
'''
    )
        exec(code, vars(module))

del Loader; del MetaPathFinder
"""
    )

    exec(definitions, glbls)

    # append the finder to the end of meta_path, in case the user
    # already has a package called micropip
    exec(
        "import sys; sys.meta_path.append(_MicropipFinder()); del sys",
        glbls,
    )


def create_main_module(
    file: str | None,
    input_override: Callable[[Any], str] | None,
    print_override: Callable[[Any], None] | None,
) -> types.ModuleType:
    # Every kernel gets its own main module, whose __dict__ attribute
    # serves as the global namespace
    _module = types.ModuleType(
        "__main__", doc="Created for the marimo kernel."
    )
    _module.__dict__.setdefault("__builtin__", globals()["__builtins__"])
    _module.__dict__.setdefault("__builtins__", globals()["__builtins__"])

    if input_override is not None:
        _module.__dict__.setdefault("input", input_override)
    if print_override is not None:
        _module.__dict__.setdefault("print", print_override)

    if file is not None:
        _module.__dict__.setdefault("__file__", file)
    elif hasattr(sys.modules["__main__"], "__file__"):
        _module.__dict__.setdefault(
            "__file__", sys.modules["__main__"].__file__
        )
    else:
        # Windows seems to have this edgecase where __file__ is not set
        # so default to None, per the intended behavior in #668.
        _module.__dict__.setdefault("__file__", None)

    return _module


def patch_main_module(
    file: str | None,
    input_override: Callable[[Any], str] | None,
    print_override: Callable[[Any], None] | None,
) -> types.ModuleType:
    """Patches __main__ module

    - Makes functions pickleable
    - Loads some overrides and mocks into globals
    """
    _module = create_main_module(file, input_override, print_override)

    # TODO(akshayka): In run mode, this can introduce races between different
    # kernel threads, since they each share sys.modules. Unfortunately, Python
    # doesn't provide a way for different threads to have their own sys.modules
    # (replacing the dict with a new one isn't guaranteed to have the intended
    # effect, since CPython C code has a reference to the original dict).
    # In practice, as far as I can tell, this only causes problems when using
    # Python pickle, but there may be other subtle issues.
    #
    # As a workaround, the runtime can re-patch sys.modules() on each run,
    # but the issue will still persist as a race condition. Streamlit suffers
    # from the same issue.
    patch_sys_module(_module)
    return _module


@contextlib.contextmanager
def patch_main_module_context(
    module: types.ModuleType,
) -> Iterator[types.ModuleType]:
    main = sys.modules["__main__"]
    try:
        sys.modules["__main__"] = module
        yield module
    finally:
        sys.modules["__main__"] = main


def patch_jedi_parameter_completion() -> None:
    import re

    from jedi.inference.compiled import (  # type: ignore[import-untyped]
        CompiledValue,
    )
    from jedi.inference.compiled.value import (  # type: ignore[import-untyped]
        SignatureParamName,
    )
    from jedi.inference.names import (  # type: ignore[import-untyped]
        AnonymousParamName,
        ParamNameWrapper,
    )
    from jedi.parser_utils import (  # type: ignore[import-untyped]
        clean_scope_docstring,
    )

    original_static_infer = AnonymousParamName.infer
    original_dynamic_infer = SignatureParamName.infer

    original_dynamic_init: Callable[..., None] = SignatureParamName.__init__

    def find_statement_documentation(tree_node: ExprStmt) -> str:
        """Find documentation of a statement (attribute in a class).

        By default jedi's `find_statement_documentation` will search
        for strings >below< attributes (not above); while that follows
        the convention of docstrings being below function signature,
        it is often contrary to what authors expect, which is comments
        above attributes in data classes.
        """
        if tree_node.type == "expr_stmt":
            maybe_name = tree_node.children[0]
            if maybe_name.type != "name":
                return ""
            maybe_comment = getattr(maybe_name, "prefix", None)
            if not isinstance(maybe_comment, str):
                return ""
            maybe_comment = maybe_comment.strip()
            if not maybe_comment.startswith("#"):
                return ""
            lines = [
                line.strip().lstrip("#") for line in maybe_comment.splitlines()
            ]
            min_indent = min(
                [len(line) - len(line.lstrip()) for line in lines]
            )
            return "\n".join(
                line.strip().lstrip("#")[min_indent:]
                for line in maybe_comment.splitlines()
            )
        return ""

    def extract_marimo_style_arguments(docstring: str) -> dict[str, str]:
        lines = docstring.splitlines()
        try:
            start = lines.index("# Arguments")
        except ValueError:
            return {}
        parsing_marimo_docstring = False
        param_descriptions: dict[str, str] = {}
        for line in lines[start + 1 :]:
            if line == "| Parameter | Type | Description |":
                parsing_marimo_docstring = True
                continue
            if line == "|-----------|------|-------------|":
                continue
            if parsing_marimo_docstring:
                if line.strip() == "" or line.startswith("#"):
                    parsing_marimo_docstring = False
                    continue
                match = re.match(
                    r"^\| `(.+)` \| `(.*)` \| (.*) \|$", line.strip()
                )
                if match:
                    param, _param_type, description = match.groups()
                    param_descriptions[param] = description
        return param_descriptions

    def extract_docstring_to_markdown_arguments(
        docstring: str,
    ) -> dict[str, str]:
        param_descriptions: dict[str, str] = {}
        lines = docstring.splitlines()
        try:
            start = lines.index("#### Parameters")
        except ValueError:
            return {}
        param = None
        for line in lines[start + 2 :]:
            if line.strip() == "" or line.startswith("#"):
                continue
            param_start = re.match(r"^\- `(.+)`:(?: (.*))?$", line.strip())
            if param_start:
                param, first_line = param_start.groups()
                param_descriptions[param] = first_line or ""
            else:
                if param:
                    if param_descriptions[param]:
                        param_descriptions[param] += "\n" + line.strip()
                    else:
                        param_descriptions[param] = line.strip()
        return param_descriptions

    def py__doc__(self: ParamNameWrapper) -> str:
        # Patch for https://github.com/davidhalter/jedi/issues/2061
        if self.tree_name is None:
            # This will only happen for runtime (imported packages)
            arg_name = self.string_name

            if self.parent_context.is_class():
                docstring = self.parent_context.py__doc__()
            else:
                docstring = self.compiled_value.py__doc__()
        else:
            # Static analysis
            definition = self.tree_name.get_definition()
            if definition.type not in {"param", "expr_stmt"}:
                return ""
            if definition.type == "expr_stmt":
                # The case of dataclasses.
                return find_statement_documentation(
                    self.tree_name.get_definition()
                )
            arg_name = definition.name.value

            if self.parent_context.is_class():
                docstring = self.parent_context.py__doc__()
            else:
                docstring = clean_scope_docstring(definition.parent.parent)

        if DependencyManager.docstring_to_markdown.has():
            from docstring_to_markdown import (  # type: ignore[import-not-found]
                UnknownFormatError,
                convert,
            )

            try:
                docstring = convert(docstring)
            except UnknownFormatError:
                return ""

        if "# Arguments" in docstring:
            param_descriptions = extract_marimo_style_arguments(docstring)
        else:
            param_descriptions = extract_docstring_to_markdown_arguments(
                docstring
            )

        if arg_name in param_descriptions:
            return param_descriptions[arg_name]
        return ""

    def filter_none_value(value: Any) -> bool:
        if not isinstance(value, CompiledValue):
            return True
        value_repr: str = value.access_handle.get_repr()
        return not (
            value_repr == "None"
            or
            # numpy's special type acting as a sentinel
            # in new and deprecated keyword arguments
            "_NoValueType" in value_repr
        )

    def wrap_infer(
        original_infer: Callable[[Any], ValueSet],
    ) -> Callable[[Any], ValueSet]:
        def infer(self: AnonymousParamName | SignatureParamName) -> ValueSet:
            # Patch for https://github.com/davidhalter/jedi/issues/2063
            result = original_infer(self)
            return result.filter(filter_none_value)

        infer.patched = True  # type: ignore[attr-defined]
        return infer

    py__doc__.patched = True  # type: ignore[attr-defined]

    def enhanced_init(
        self: SignatureParamName,
        compiled_value: CompiledValue,
        signature_param: str,
    ) -> None:
        original_dynamic_init(self, compiled_value, signature_param)
        self.compiled_value = compiled_value

    enhanced_init.patched = True  # type: ignore[attr-defined]

    if not (
        hasattr(ParamNameWrapper, "py__doc__")
        and getattr(ParamNameWrapper.py__doc__, "patched", False)
    ):
        ParamNameWrapper.py__doc__ = py__doc__
    if not (
        hasattr(AnonymousParamName, "infer")
        and getattr(AnonymousParamName.infer, "patched", False)
    ):
        AnonymousParamName.infer = wrap_infer(original_static_infer)

    if not getattr(SignatureParamName.infer, "patched", False):
        SignatureParamName.infer = wrap_infer(original_dynamic_infer)
    if not getattr(SignatureParamName.__init__, "patched", False):
        SignatureParamName.__init__ = enhanced_init


def patch_polars_write_json() -> Unpatch:
    """Patch polars.DataFrame.write_json to work in WASM environments.

    In WASM, file system operations may fail. This patch attempts to use
    write_json first, and if it fails, falls back to write_csv and then
    converts the CSV to JSON.
    """
    if not is_pyodide():
        return lambda: None

    import io
    import pathlib

    import polars

    original_write_json = polars.DataFrame.write_json

    def patched_write_json(
        self: polars.DataFrame,
        file: io.IOBase | str | pathlib.Path | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> str | None:
        try:
            # First try the original method
            return original_write_json(self, file, *args, **kwargs)
        except Exception:
            # Fallback to CSV
            import json

            buffer = io.BytesIO()

            # Write to CSV
            self.write_csv(buffer)

            # Read CSV as text
            buffer.seek(0)
            csv_content = buffer.read().decode("utf-8")

            # Parse CSV to create JSON
            lines = csv_content.strip().split("\n")
            json_data: list[dict[str, str]] = []
            if lines:
                headers: list[str] = lines[0].split(",")
                for line in lines[1:]:
                    values: list[str] = line.split(",")
                    json_data.append(dict(zip(headers, values)))

            if file is None:
                return json.dumps(json_data)
            elif isinstance(file, io.IOBase):
                json.dump(json_data, file)
            elif isinstance(file, pathlib.Path):
                file.write_text(json.dumps(json_data))
            else:
                with open(file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f)

            return None

    # Apply the patch
    polars.DataFrame.write_json = patched_write_json  # type: ignore

    def unpatch_polars_write_json() -> None:
        polars.DataFrame.write_json = original_write_json  # type: ignore

    return unpatch_polars_write_json

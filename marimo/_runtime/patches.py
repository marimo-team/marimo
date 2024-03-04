# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import functools
import sys
import textwrap
import types
from typing import Any, Callable, Iterator

from marimo._runtime import marimo_pdb


def patch_pdb(debugger: marimo_pdb.MarimoPdb) -> None:
    import pdb

    # Patch Pdb so manually instantiated debuggers create our debugger
    pdb.Pdb = marimo_pdb.MarimoPdb  # type: ignore[misc, assignment]
    pdb.set_trace = functools.partial(marimo_pdb.set_trace, debugger=debugger)


def patch_sys_module(module: types.ModuleType) -> None:
    sys.modules[module.__name__] = module


def patch_micropip(glbls: dict[Any, Any]) -> None:
    """Mock micropip with no-ops"""

    definitions = textwrap.dedent(
        """\
from importlib.abc import Loader, MetaPathFinder

class _MicropipFinder(MetaPathFinder):


    def find_spec(self, fullname, path, target=None):
        from importlib.util import spec_from_loader

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


def patch_main_module(
    file: str | None, input_override: Callable[[Any], str] | None
) -> types.ModuleType:
    """Patches __main__ module

    - Makes functions pickleable
    - Loads some overrides and mocks into globals
    """

    # Every kernel gets its own main module, whose __dict__ attribute
    # serves as the global namespace
    _module = types.ModuleType(
        "__main__", doc="Created for the marimo kernel."
    )
    _module.__dict__.setdefault("__builtin__", globals()["__builtins__"])
    _module.__dict__.setdefault("__builtins__", globals()["__builtins__"])

    if input_override is not None:
        _module.__dict__.setdefault("input", input_override)

    if file is not None:
        _module.__dict__.setdefault("__file__", file)
    else:
        _module.__dict__.setdefault(
            "__file__", sys.modules["__main__"].__file__
        )

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
    file: str | None = None, input_override: Callable[[Any], str] | None = None
) -> Iterator[types.ModuleType]:
    main = sys.modules["__main__"]
    try:
        yield patch_main_module(file, input_override)
    finally:
        sys.modules["__main__"] = main

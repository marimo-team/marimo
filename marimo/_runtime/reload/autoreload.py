# Copyright 2024 Marimo. All rights reserved.
"""Module reloader

In addition to reloading modules, the reloader also patches instances
of reloaded objects with their code.

Based on the autoreload extension from the IPython project (BSD-3 Clause).
"""

from __future__ import annotations

import gc
import io
import modulefinder
import os
import sys
import threading
import traceback
import types
import warnings
import weakref
from dataclasses import dataclass
from importlib import reload
from importlib.util import source_from_cache
from typing import Any, Callable, Dict, Generic, List, Tuple, Type, TypeVar

from marimo import _loggers
from marimo._ast.cell import CellImpl
from marimo._messaging.tracebacks import write_traceback

LOGGER = _loggers.marimo_logger()

func_attrs = [
    "__code__",
    "__defaults__",
    "__doc__",
    "__closure__",
    "__globals__",
    "__dict__",
]


@dataclass
class ModuleMTime:
    name: str
    mtime: float


# (module-name, name) -> weakref, for replacing old code objects
OldObjectsMapping = Dict[
    Tuple[str, str], List[weakref.ref]  # type:ignore[type-arg]
]


def modules_imported_by_cell(
    cell: CellImpl, sys_modules: dict[str, types.ModuleType]
) -> set[str]:
    """Get the modules imported by a cell"""
    modules = set()
    for import_data in cell.imports:
        if import_data.module in sys_modules:
            modules.add(import_data.module)
        if import_data.imported_symbol in sys_modules:
            # The imported symbol may or may not be a module, which
            # is why we check if it's in sys.modules
            #
            # e.g., from a import b
            #
            # a.b could be a module, but it could also be a function, ...
            modules.add(import_data.imported_symbol)
    return modules


class ModuleDependencyFinder:
    def __init__(self) -> None:
        # __file__ ->
        self._module_dependencies: dict[str, dict[str, types.ModuleType]] = {}
        self._failed_module_filenames: set[str] = set()

    def find_dependencies(
        self, module: types.ModuleType, excludes: list[str]
    ) -> dict[str, types.ModuleType]:
        if not hasattr(module, "__file__") or module.__file__ is None:
            return {}

        file = module.__file__
        if module.__file__ in self._failed_module_filenames:
            return {}

        if file in self._module_dependencies:
            return self._module_dependencies[file]

        finder = modulefinder.ModuleFinder(excludes=excludes)
        try:
            with warnings.catch_warnings():
                # We temporarily ignore warnings to avoid spamming the console,
                # since the watcher runs in a loop
                warnings.simplefilter("ignore")
                finder.run_script(module.__file__)
        except SyntaxError:
            # user introduced a syntax error, maybe; still check if the
            # module itself has been modified
            return {}
        except Exception:
            # some modules like numpy fail when called with run_script;
            # run_script takes a long time before failing on them, so
            # don't try to analyze them again
            self._failed_module_filenames.add(file)
            return {}
        else:
            # False positives
            self._module_dependencies[file] = finder.modules  # type: ignore[assignment]
            return finder.modules  # type: ignore[return-value]

    def cached(self, module: types.ModuleType) -> bool:
        if not hasattr(module, "__file__") or module.__file__ is None:
            return False

        return module.__file__ in self._module_dependencies

    def evict_from_cache(self, module: types.ModuleType) -> None:
        file = module.__file__
        if file in self._module_dependencies:
            del self._module_dependencies[file]


class ModuleReloader:
    """Thread-safe module reloader."""

    def __init__(self) -> None:
        # Modules that failed to reload: {module: mtime-on-failed-reload, ...}
        self.failed: dict[str, float] = {}
        # For replacing old code objects
        self.old_objects: OldObjectsMapping = {}
        # module-name -> mtime (module modification timestamps)
        self.modules_mtimes: dict[str, float] = {}
        # set of modules names known to be stale but haven't been reloaded
        self.stale_modules: set[str] = set()
        # for thread-safety
        self.lock = threading.Lock()
        self._module_dependency_finder = ModuleDependencyFinder()

        # Timestamp existing modules
        self.check(modules=sys.modules, reload=False)

    def filename_and_mtime(
        self, module: types.ModuleType
    ) -> ModuleMTime | None:
        if not hasattr(module, "__file__") or module.__file__ is None:
            return None

        if getattr(module, "__name__", None) in [
            None,
            "__mp_main__",
            "__main__",
            "sys",
            "builtins",
        ]:
            # we cannot reload(__main__) or reload(__mp_main__);
            # Python advises against reloading sys and builtins
            return None

        filename = module.__file__
        _, ext = os.path.splitext(filename)

        if ext.lower() == ".py":
            py_filename = filename
        else:
            try:
                py_filename = source_from_cache(filename)
            except ValueError:
                return None

        try:
            pymtime = os.stat(py_filename).st_mtime
        except OSError:
            return None
        return ModuleMTime(py_filename, pymtime)

    def cell_uses_stale_modules(self, cell: CellImpl) -> bool:
        with self.lock:
            return bool(
                self.stale_modules
                & modules_imported_by_cell(cell, sys.modules)
            )

    def check(
        self, modules: dict[str, types.ModuleType], reload: bool
    ) -> set[types.ModuleType]:
        """Check timestamps of modules, optionally reload them.

        Also patches existing objects with hot-reloaded ones.

        Returns a set of modules that were found to have been modified.
        """

        # module watcher thread and kernel thread might try to use the
        # reloader at the same time, but reloader mutates state
        #
        # Holds a lock because this method modifies stale_modules
        # and also iterates over it
        with self.lock:
            modified_modules: set[types.ModuleType] = set()
            # materialize the module keys, since we'll be reloading while
            # iterating
            for modname in list(modules.keys()):
                m = modules.get(modname, None)
                if m is None:
                    continue

                module_mtime = self.filename_and_mtime(m)
                if module_mtime is None:
                    continue
                py_filename, pymtime = module_mtime.name, module_mtime.mtime

                try:
                    if pymtime <= self.modules_mtimes[modname]:
                        continue
                except KeyError:
                    self.modules_mtimes[modname] = pymtime
                    continue
                else:
                    if self.failed.get(py_filename, None) == pymtime:
                        continue

                self.modules_mtimes[modname] = pymtime
                modified_modules.add(m)
                self.stale_modules.add(modname)
                self._module_dependency_finder.evict_from_cache(m)

            if not reload:
                return modified_modules

            for modname in self.stale_modules:
                # Reload after the check loop: if there are any
                # previously discovered stale modules, reload those as well
                m = modules.get(modname, None)
                if m is None:
                    continue

                module_mtime = self.filename_and_mtime(m)
                if module_mtime is None:
                    continue
                py_filename, pymtime = module_mtime.name, module_mtime.mtime

                LOGGER.debug(f"Reloading '{modname}'.")
                try:
                    superreload(m, self.old_objects)
                    if py_filename in self.failed:
                        del self.failed[py_filename]
                except Exception:
                    msg = "[autoreload of {} failed: {}]"
                    LOGGER.debug(
                        msg.format(modname, traceback.format_exc(10)),
                    )
                    self.failed[py_filename] = pymtime
                else:
                    # TODO or always evict?
                    self._module_dependency_finder.evict_from_cache(m)

            self.stale_modules.clear()
        return modified_modules

    def get_module_dependencies(
        self, module: types.ModuleType, excludes: list[str]
    ) -> dict[str, types.ModuleType]:
        return self._module_dependency_finder.find_dependencies(
            module, excludes
        )


def update_function(old: object, new: object) -> None:
    """Upgrade the code object of a function"""
    for name in func_attrs:
        try:
            setattr(old, name, getattr(new, name))
        except (AttributeError, TypeError):
            pass


def update_instances(old: object, new: object) -> None:
    """Use garbage collector to find all instances that refer to the old
    class definition and update their __class__ to point to the new class
    definition"""

    refs = gc.get_referrers(old)

    for ref in refs:
        if type(ref) is old:
            object.__setattr__(ref, "__class__", new)


def update_class(old: object, new: object) -> None:
    """Replace stuff in the __dict__ of a class, and upgrade
    method code objects, and add new methods, if any"""
    for key in list(old.__dict__.keys()):
        old_obj = getattr(old, key)
        new_obj: object | None = None
        try:
            new_obj = getattr(new, key)
            # explicitly checking that comparison returns True to handle
            # cases where `==` doesn't return a boolean.
            if (old_obj == new_obj) is True:
                continue
        except AttributeError:
            # obsolete attribute: remove it
            try:
                delattr(old, key)
            except (AttributeError, TypeError):
                pass
            continue
        except ValueError:
            # can't compare nested structures containing
            # numpy arrays using `==`
            pass

        if new_obj is None or update_generic(old_obj, new_obj):
            continue

        try:
            setattr(old, key, getattr(new, key))
        except (AttributeError, TypeError):
            pass  # skip non-writable attributes

    for key in list(new.__dict__.keys()):
        if key not in list(old.__dict__.keys()):
            try:
                setattr(old, key, getattr(new, key))
            except (AttributeError, TypeError):
                pass  # skip non-writable attributes

    # update all instances of class
    update_instances(old, new)


def update_property(old: object, new: object) -> None:
    """Replace get/set/del functions of a property"""
    update_generic(old.fdel, new.fdel)  # type:ignore[attr-defined]
    update_generic(old.fget, new.fget)  # type:ignore[attr-defined]
    update_generic(old.fset, new.fset)  # type:ignore[attr-defined]


def isinstance2(a: object, b: object, typ: Type[Any]) -> bool:
    return isinstance(a, typ) and isinstance(b, typ)


UPDATE_RULES: list[
    tuple[Callable[[object, object], bool], Callable[[object, object], None]]
] = [
    (lambda a, b: isinstance2(a, b, type), update_class),
    (lambda a, b: isinstance2(a, b, types.FunctionType), update_function),
    (lambda a, b: isinstance2(a, b, property), update_property),
]
UPDATE_RULES.extend(
    [
        (
            lambda a, b: isinstance2(a, b, types.MethodType),
            lambda a, b: update_function(a.__func__, b.__func__),  # type: ignore[attr-defined]  # noqa: E501
        ),
    ]
)


def update_generic(a: object, b: object) -> bool:
    for type_check, update in UPDATE_RULES:
        if type_check(a, b):
            update(a, b)
            return True
    return False


T = TypeVar("T")


class StrongRef(Generic[T]):
    def __init__(self, obj: T) -> None:
        self.obj = obj

    def __call__(self) -> T:
        return self.obj


def append_obj(
    module: types.ModuleType,
    d: OldObjectsMapping,
    # object name
    name: str,
    obj: object,
) -> bool:
    in_module = (
        hasattr(obj, "__module__") and obj.__module__ == module.__name__
    )
    if not in_module:
        return False

    key = (module.__name__, name)
    try:
        d.setdefault(key, []).append(weakref.ref(obj))
    except TypeError:
        pass
    return True


def superreload(
    module: types.ModuleType, old_objects: OldObjectsMapping | None
) -> types.ModuleType:
    """Enhanced version of the builtin reload function.

    superreload remembers objects previously in the module, and

    - upgrades the class dictionary of every old class in the module
    - upgrades the code object of every old function and method
    - clears the module's namespace before reloading

    """
    if old_objects is None:
        old_objects = {}

    # collect old objects in the module
    for name, obj in list(module.__dict__.items()):
        if not append_obj(module, old_objects, name, obj):
            continue
        key = (module.__name__, name)
        try:
            old_objects.setdefault(key, []).append(weakref.ref(obj))
        except TypeError:
            pass

    # reload module
    old_dict: dict[str, Any] | None = None
    try:
        # clear namespace first from old cruft
        old_dict = module.__dict__.copy()
        old_name = module.__name__
        module.__dict__.clear()
        module.__dict__["__name__"] = old_name
        module.__dict__["__loader__"] = old_dict["__loader__"]
    except (TypeError, AttributeError, KeyError):
        pass

    try:
        module = reload(module)
    except Exception as e:
        # User introduced a SyntaxError, ModuleNotFoundError, etc -- they
        # should be told, and module dict should not be restored, ie don't fail
        # silently.
        #
        # It's possible that the module fails to reload for some other reason.
        # In this case, too, the failure shouldn't be silent!
        sys.stderr.write(
            f"Error trying to reload module {module.__name__}: {str(e)} \n"
        )
        tmpio = io.StringIO()
        traceback.print_exc(file=tmpio)
        tmpio.seek(0)
        write_traceback(tmpio.read())
        raise

    # iterate over all objects and update functions & classes
    for name, new_obj in list(module.__dict__.items()):
        key = (module.__name__, name)
        if key not in old_objects:
            continue

        new_refs = []
        for old_ref in old_objects[key]:
            old_obj = old_ref()
            if old_obj is None:
                continue
            new_refs.append(old_ref)
            update_generic(old_obj, new_obj)

        if new_refs:
            old_objects[key] = new_refs
        else:
            del old_objects[key]

    return module

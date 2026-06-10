# Copyright 2026 Marimo. All rights reserved.
"""Install process-shaped multiprocessing patches for Pyodide."""

from __future__ import annotations

import queue as _queue
import sys
from dataclasses import dataclass
from importlib import import_module
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._concurrency import _state
from marimo._runtime._wasm._concurrency._mp_context import (
    cpu_count,
    freeze_support,
    get_all_start_methods,
    get_context_factory,
    get_start_method,
    set_start_method,
    unsupported_factory,
    validate_start_method,
)
from marimo._runtime._wasm._concurrency._mp_process import (
    AsyncProcess,
    active_children,
    current_process,
    parent_process,
)
from marimo._runtime._wasm._concurrency._mp_queue import (
    AsyncProcessQueue,
    AsyncProcessSimpleQueue,
    direct_queue_factory,
    direct_simple_queue_factory,
    queue_factory,
    simple_queue_factory,
)
from marimo._runtime._wasm._patches import Unpatch, WasmPatchSet
from marimo._utils.platform import is_pyodide

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class MultiprocessingPatch:
    attr: str
    replacement: Callable[..., Any]


TOP_LEVEL_FACTORIES = (
    MultiprocessingPatch("Process", AsyncProcess),
    MultiprocessingPatch("Queue", direct_queue_factory),
    MultiprocessingPatch("SimpleQueue", direct_simple_queue_factory),
)

TOP_LEVEL_HELPERS = (
    MultiprocessingPatch("cpu_count", cpu_count),
    MultiprocessingPatch("get_all_start_methods", get_all_start_methods),
    MultiprocessingPatch("get_start_method", get_start_method),
    MultiprocessingPatch("set_start_method", set_start_method),
    MultiprocessingPatch("current_process", current_process),
    MultiprocessingPatch("parent_process", parent_process),
    MultiprocessingPatch("active_children", active_children),
    MultiprocessingPatch("freeze_support", freeze_support),
)

PROCESS_MODULE_HELPERS = (
    MultiprocessingPatch("current_process", current_process),
    MultiprocessingPatch("parent_process", parent_process),
    MultiprocessingPatch("active_children", active_children),
)

BLOCKED_FACTORIES = ("JoinableQueue",)


def install_wasm_process_shims() -> Unpatch:
    """Patch process-shaped multiprocessing APIs in Pyodide."""
    if not is_pyodide():
        return lambda: None
    if _state.active_process_unpatch() is not None:
        return lambda: None
    try:
        _state.patch_state()
    except RuntimeError as exc:
        raise RuntimeError(
            "WASM concurrency shims must be installed before process shims"
        ) from exc

    import multiprocessing
    import multiprocessing.context as multiprocessing_context
    import multiprocessing.process as multiprocessing_process

    patches = WasmPatchSet()
    try:
        multiprocessing_queues = _optional_import(
            "multiprocessing.queues"
        ) or _create_submodule(
            patches, multiprocessing, "multiprocessing.queues", "queues"
        )
        _install_multiprocessing_process(
            patches,
            multiprocessing=multiprocessing,
            multiprocessing_context=multiprocessing_context,
            multiprocessing_process=multiprocessing_process,
            multiprocessing_queues=multiprocessing_queues,
        )
    except BaseException:
        patches.unpatch_all()()
        raise

    unpatch = patches.unpatch_all()

    def _run_unpatch() -> None:
        try:
            unpatch()
        finally:
            _state.set_active_process_unpatch(None)

    _state.set_active_process_unpatch(_run_unpatch)

    def _guarded_unpatch() -> None:
        unpatch_wasm_process_shims()

    return _guarded_unpatch


def unpatch_wasm_process_shims() -> None:
    """Remove active process-shaped multiprocessing patches."""
    unpatch = _state.active_process_unpatch()
    if unpatch is None:
        return
    _state.discard_finished_runtime_records()
    if _state.has_live_process_work():
        raise RuntimeError("Cannot unpatch while WASM process work is live")
    unpatch()


def _install_multiprocessing_process(
    patches: WasmPatchSet,
    *,
    multiprocessing: Any,
    multiprocessing_context: Any,
    multiprocessing_process: Any,
    multiprocessing_queues: ModuleType,
) -> None:
    for spec in TOP_LEVEL_FACTORIES:
        patches.replace(
            multiprocessing,
            spec.attr,
            _constant_replacement(spec.replacement),
        )
    for attr in BLOCKED_FACTORIES:
        patches.replace(
            multiprocessing,
            attr,
            _unsupported_multiprocessing_factory(attr),
        )
    for spec in TOP_LEVEL_HELPERS:
        patches.replace(
            multiprocessing,
            spec.attr,
            _constant_replacement(spec.replacement),
        )
    patches.replace(
        multiprocessing,
        "get_context",
        lambda original: get_context_factory(original),
    )

    _replace_factories(
        patches,
        multiprocessing_process,
        PROCESS_MODULE_HELPERS,
    )
    _replace_queue_submodule_factories(patches, multiprocessing_queues)
    _replace_context_processes(patches, multiprocessing_context)
    _replace_context_helpers(patches, multiprocessing_context)


def _replace_context_processes(
    patches: WasmPatchSet,
    multiprocessing_context: Any,
) -> None:
    for attr in ("Process", "SpawnProcess"):
        patches.replace(
            multiprocessing_context,
            attr,
            _constant_replacement(AsyncProcess),
        )
    for context_name in ("DefaultContext", "SpawnContext"):
        context_type = getattr(multiprocessing_context, context_name, None)
        if context_type is not None:
            patches.replace(
                context_type,
                "Process",
                _constant_replacement(AsyncProcess),
            )
    for context_name in ("ForkContext", "ForkServerContext"):
        context_type = getattr(multiprocessing_context, context_name, None)
        if context_type is not None:
            patches.replace(
                context_type,
                "Process",
                _constant_replacement(
                    unsupported_factory(f"{context_name}.Process")
                ),
            )


def _replace_context_helpers(
    patches: WasmPatchSet,
    multiprocessing_context: Any,
) -> None:
    base_context = getattr(multiprocessing_context, "BaseContext", None)
    if base_context is not None:
        patches.replace(
            base_context,
            "Queue",
            _constant_replacement(queue_factory),
        )
        patches.replace(
            base_context,
            "SimpleQueue",
            _constant_replacement(simple_queue_factory),
        )
        patches.replace(
            base_context,
            "JoinableQueue",
            _unsupported_context_factory("JoinableQueue"),
        )
        patches.replace_descriptor(
            base_context,
            "current_process",
            lambda _original: staticmethod(current_process),
        )
        patches.replace_descriptor(
            base_context,
            "parent_process",
            lambda _original: staticmethod(parent_process),
        )
        patches.replace_descriptor(
            base_context,
            "active_children",
            lambda _original: staticmethod(active_children),
        )
        patches.replace(
            base_context,
            "cpu_count",
            lambda _original: _context_cpu_count,
        )

    default_context = getattr(multiprocessing_context, "DefaultContext", None)
    if default_context is None:
        return
    patches.replace(
        default_context,
        "get_context",
        _default_context_get_context_factory,
    )
    patches.replace(
        default_context,
        "set_start_method",
        lambda _original: _default_context_set_start_method,
    )
    patches.replace(
        default_context,
        "get_start_method",
        lambda _original: _default_context_get_start_method,
    )
    patches.replace(
        default_context,
        "get_all_start_methods",
        lambda _original: _default_context_get_all_start_methods,
    )


def _constant_replacement(value: Any) -> Callable[[Any], Any]:
    def _factory(_original: Any) -> Any:
        del _original
        return value

    return _factory


def _unsupported_multiprocessing_factory(attr: str) -> Callable[[Any], Any]:
    def _factory(_original: Any) -> Any:
        del _original
        return unsupported_factory(f"multiprocessing.{attr}")

    return _factory


def _unsupported_context_factory(attr: str) -> Callable[[Any], Any]:
    def _factory(_original: Any) -> Any:
        del _original
        return unsupported_factory(f"multiprocessing.context.{attr}")

    return _factory


def _replace_factories(
    patches: WasmPatchSet,
    module: Any,
    specs: tuple[MultiprocessingPatch, ...],
) -> None:
    for spec in specs:
        patches.replace(
            module,
            spec.attr,
            _constant_replacement(spec.replacement),
        )


def _replace_queue_submodule_factories(
    patches: WasmPatchSet,
    module: ModuleType,
) -> None:
    _replace_or_add(patches, module, "Empty", _queue.Empty)
    _replace_or_add(patches, module, "Full", _queue.Full)
    _replace_or_add(patches, module, "Queue", AsyncProcessQueue)
    _replace_or_add(patches, module, "SimpleQueue", AsyncProcessSimpleQueue)
    _replace_or_add(
        patches,
        module,
        "JoinableQueue",
        unsupported_factory("multiprocessing.queues.JoinableQueue"),
    )


def _replace_or_add(
    patches: WasmPatchSet,
    module: ModuleType,
    attr: str,
    replacement: Any,
) -> None:
    if hasattr(module, attr):
        patches.replace(module, attr, lambda _original: replacement)
        return
    setattr(module, attr, replacement)

    def _remove() -> None:
        if getattr(module, attr, None) is replacement:
            delattr(module, attr)

    patches.add_cleanup(_remove)


def _optional_import(module_name: str) -> ModuleType | None:
    try:
        return import_module(module_name)
    except (ImportError, OSError):
        return None


def _create_submodule(
    patches: WasmPatchSet,
    parent: Any,
    module_name: str,
    parent_attr: str,
) -> ModuleType:
    module = ModuleType(module_name)
    module.__spec__ = ModuleSpec(module_name, loader=None)
    had_parent_attr = hasattr(parent, parent_attr)
    original_parent_attr = getattr(parent, parent_attr, None)
    sys.modules[module_name] = module
    setattr(parent, parent_attr, module)

    def _remove() -> None:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        if getattr(parent, parent_attr, None) is module:
            if had_parent_attr:
                setattr(parent, parent_attr, original_parent_attr)
            else:
                delattr(parent, parent_attr)

    patches.add_cleanup(_remove)
    return module


def _default_context_get_context_factory(
    original: Callable[..., Any],
) -> Callable[..., Any]:
    def _get_context(self: Any, method: str | None = None) -> Any:
        validate_start_method(method)
        return original(self, "spawn")

    return _get_context


def _context_cpu_count(self: Any) -> int:
    del self
    return cpu_count()


def _default_context_set_start_method(
    self: Any, method: str | None, force: bool = False
) -> None:
    del self
    set_start_method(method, force=force)


def _default_context_get_start_method(
    self: Any, allow_none: bool = False
) -> str:
    del self
    return get_start_method(allow_none=allow_none)


def _default_context_get_all_start_methods(self: Any) -> list[str]:
    del self
    return get_all_start_methods()

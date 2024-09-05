# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import weakref
from typing import Any, Dict, Iterable, Mapping, Optional, TypeVar, Union

from marimo._runtime.context.types import ContextNotInitializedError

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

from marimo._ast.app import _Namespace
from marimo._ast.cell import CellId_t
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context

UIElementId = str

T = TypeVar("T")

# Recursive types don't support | or dict[] in py3.8/3.9
LensValue: TypeAlias = Union[T, Dict[str, "LensValue[T]"]]


class UIElementRegistry:
    def __init__(self) -> None:
        # mapping from object id to UIElement object that has that id
        self._objects: dict[UIElementId, weakref.ref[UIElement[Any, Any]]] = {}
        # mapping from object id to set of names that are bound to it
        self._bindings: dict[UIElementId, set[str]] = {}
        # mapping from object id to cell that created it
        self._constructing_cells: dict[UIElementId, CellId_t] = {}

    def register(
        self,
        object_id: UIElementId,
        ui_element: UIElement[Any, Any],
    ) -> None:
        execution_context = get_context().execution_context
        if object_id in self._objects:
            # on cell re-run, a UI element may be (re)-registered before
            # its destructor was called, so manually delete the old element
            # here
            self.delete(object_id, id(self._objects[object_id]))
        self._objects[object_id] = weakref.ref(ui_element)
        assert execution_context is not None
        self._constructing_cells[object_id] = execution_context.cell_id
        # bindings must be lazily registered, since there aren't any
        # bindings at UIElement object creation time
        if object_id in self._bindings:
            # If `register` is called on an object_id that is being
            # reused before `delete` is called, bindings won't have been
            # cleaned up
            del self._bindings[object_id]

    def bound_names(self, object_id: UIElementId) -> Iterable[str]:
        if object_id not in self._bindings:
            self._register_bindings(object_id)
        return self._bindings[object_id]

    def _has_parent_id(
        self, child: UIElement[Any, Any], parent_id: UIElementId
    ) -> bool:
        """Returns True if `child` has id `parent_id` or is a view of it"""
        if child._id == parent_id:
            return True
        elif child._lens is not None:
            element_ref = self._objects.get(child._lens.parent_id)
            element = element_ref() if element_ref is not None else None
            if element is not None:
                return self._has_parent_id(element, parent_id)
        return False

    def _find_bindings_in_namespace(
        self, object_id: UIElementId, glbls: Mapping[str, Any]
    ) -> set[str]:
        # Get all variable names that are either:
        #   1. bound to this UI element, or
        #   2. bound to a view (child) of this element
        #
        # Also introspects _Namespace objects, including the name of the
        # _Namespace if it contains `object_id`
        bindings: set[str] = set()
        for name, value in glbls.items():
            if isinstance(value, UIElement) and self._has_parent_id(
                value, object_id
            ):
                bindings.add(name)
            elif isinstance(
                value, _Namespace
            ) and self._find_bindings_in_namespace(object_id, value):
                bindings.add(name)
        return bindings

    def _register_bindings(
        self, object_id: UIElementId, glbls: Optional[dict[str, Any]] = None
    ) -> None:
        from marimo._runtime.context.kernel_context import KernelRuntimeContext

        ctx = get_context()
        if isinstance(ctx, KernelRuntimeContext) or glbls is not None:
            if glbls is None:
                glbls = ctx.globals
            self._bindings[object_id] = self._find_bindings_in_namespace(
                object_id, glbls
            )

    def register_scope(
        self, glbls: dict[str, Any], defs: Optional[set[str]] = None
    ) -> None:
        if defs is None:
            defs = set(glbls.keys())
        for binding in defs:
            lookup = glbls.get(binding, None)
            if isinstance(lookup, UIElement):
                self._register_bindings(lookup._id, glbls)

    def lookup(self, name: str) -> Optional[UIElement[Any, Any]]:
        for object_id, bindings in self._bindings.items():
            if name in bindings:
                return self.get_object(object_id)
        return None

    def get_object(self, object_id: UIElementId) -> UIElement[Any, Any]:
        if object_id not in self._objects:
            raise KeyError(f"UIElement with id {object_id} not found")
        obj = self._objects[object_id]()
        assert obj is not None
        return obj

    def get_cell(self, object_id: UIElementId) -> CellId_t:
        return self._constructing_cells[object_id]

    def resolve_lens(
        self, object_id: UIElementId, value: LensValue[T]
    ) -> tuple[str, LensValue[T]]:
        """Resolve a lens, if any, to an object id and value update

        Returns (resolved object id, resolved value)

        Raises KeyError if `object_id` does not exist in the registry,
        RuntimeError if the object was deleted.
        """
        if object_id not in self._objects:
            raise KeyError(f"UIElement with id {object_id} not found")
        obj = self._objects[object_id]()
        if obj is None:
            raise RuntimeError(f"UIElement with id {object_id} was deleted")

        lens = obj._lens
        if lens is None:
            # Base case: the element has no lens, so the resolved
            # update is the same as what was passed in.
            return (object_id, value)

        resolved_value = {lens.key: value}
        return self.resolve_lens(lens.parent_id, resolved_value)

    def delete(self, object_id: UIElementId, python_id: int) -> None:
        """Delete a UI element from the registry

        This function may be called by the Python garbage collector, while
        a cell is executing. For this reason we make sure not to log
        anything -- these logs would show up as console output in the
        frontend, confusing the user.
        """
        if object_id not in self._objects:
            return

        ui_element = self._objects[object_id]()
        # We guard against UIElement's destructor racing against
        # registration of another element when a cell re-runs by checking
        # the Python object id. This isn't perfect because python ids can
        # be reused ...
        registered_python_id = (
            id(ui_element) if ui_element is not None else None
        )
        if (
            registered_python_id is not None
            and registered_python_id != python_id
        ):
            return

        try:
            ctx = get_context()
        except ContextNotInitializedError:
            pass
        else:
            ctx.function_registry.delete(namespace=object_id)

        if object_id in self._bindings:
            del self._bindings[object_id]
        if object_id in self._constructing_cells:
            del self._constructing_cells[object_id]
        del self._objects[object_id]

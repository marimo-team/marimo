# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from typing import Any, Iterable

from marimo import _loggers
from marimo._ast.cell import CellId_t
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context

UIElementId = str
LOGGER = _loggers.marimo_logger()


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
        kernel = get_context().kernel
        self._objects[object_id] = weakref.ref(ui_element)
        assert kernel.execution_context is not None
        self._constructing_cells[object_id] = kernel.execution_context.cell_id
        if object_id in self._bindings:
            # If `register` is called on an object_id that is being
            # reused before `delete` is called, bindings won't have been
            # cleaned up
            del self._bindings[object_id]

    def bound_names(self, object_id: UIElementId) -> Iterable[str]:
        if object_id not in self._bindings:
            self._register_bindings(object_id)
        return self._bindings[object_id]

    def _register_bindings(self, object_id: UIElementId) -> None:
        kernel = get_context().kernel
        names = set(
            [
                name
                for name in kernel.globals
                if (
                    isinstance(kernel.globals[name], UIElement)
                    and kernel.globals[name]._id == object_id
                )
            ]
        )
        self._bindings[object_id] = names

    def delete(self, object_id: UIElementId, python_id: int) -> None:
        if object_id not in self._objects:
            return

        registered_python_id = id(self._objects[object_id]())
        if registered_python_id != python_id:
            LOGGER.debug(
                "Python id mismatch when deleting UI element %s", object_id
            )
            return

        if self._objects[object_id]:
            del self._objects[object_id]
        if object_id in self._bindings:
            del self._bindings[object_id]
        if object_id in self._constructing_cells:
            del self._constructing_cells[object_id]

    def get_object(self, object_id: UIElementId) -> UIElement[Any, Any]:
        if object_id not in self._objects:
            raise KeyError(f"UIElement with id {object_id} not found")
        # UI elements are only updated if a global is bound to it. This ensures
        # that the UI element update triggers reactivity, but also means that
        # elements stored as, say, attributes on an object won't be updated.
        if not self.bound_names(object_id):
            raise NameError(f"UIElement with id {object_id} has no bindings")
        obj = self._objects[object_id]()
        assert obj is not None
        return obj

    def get_cell(self, object_id: UIElementId) -> CellId_t:
        return self._constructing_cells[object_id]
